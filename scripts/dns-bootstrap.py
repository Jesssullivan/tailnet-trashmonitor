#!/usr/bin/env python3
"""
Idempotently reconcile DNS for the trashmonitor tailnet alias.

What it does:
  1. Reads the Cloudflare API token from $CF_API_TOKEN and the
     Tailscale API key from $TS_API_KEY.
  2. Ensures the configured Cloudflare zone has an A record:
       <DNS_HOSTNAME> -> <tailnet IP>
     where <tailnet IP> is discovered from `tailscale status` (so the
     record self-heals if the trashmonitor proxy ever gets reassigned
     a different tailnet address).
  3. Ensures the Tailscale tailnet split-DNS map contains:
       <DNS_ZONE> -> 1.1.1.1, 1.0.0.1
     so tailnet clients can resolve the alias without local resolver
     fights.

Idempotent: re-running with no changes is a no-op (prints "ok" per
check). Exits non-zero if anything fails.

Why an A record and not a CNAME to the .ts.net hostname: public
resolvers can't follow CNAMEs into Tailscale MagicDNS, which only
answers to tailnet clients. The A-to-CGNAT-IP works because the IP
is publicly resolvable but only routable from tailnet.

Configuration (all required unless noted):
  CF_API_TOKEN     Cloudflare API token (zone:dns:edit on DNS_ZONE)
  TS_API_KEY       Tailscale API key (dns:write)
  TS_TAILNET       Tailnet name (e.g. example.com or your-org.ts.net)
  TS_HOSTNAME      Tailnet hostname of the workload (e.g. trashmonitor)
  DNS_ZONE         Cloudflare zone (e.g. example.com)
  DNS_HOSTNAME     FQDN to publish (e.g. trashmonitor.example.com)

Optional:
  SPLIT_DNS_RESOLVERS  Comma-separated resolvers for the split-DNS map.
                       Default: 1.1.1.1,1.0.0.1
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from typing import Any
from urllib import error, request


def env(name: str) -> str:
	v = os.environ.get(name)
	if not v:
		sys.exit(f"error: ${name} must be set (see header of dns-bootstrap.py)")
	return v


def http(method: str, url: str, token: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
	data = json.dumps(body).encode() if body is not None else None
	req = request.Request(
		url,
		data=data,
		method=method,
		headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
	)
	try:
		with request.urlopen(req, timeout=20) as resp:
			return json.loads(resp.read())
	except error.HTTPError as e:
		return json.loads(e.read())


def find_tailnet_ip(hostname: str) -> str:
	if not shutil.which("tailscale"):
		sys.exit("error: `tailscale` binary not found in PATH")
	out = subprocess.check_output(["tailscale", "status", "--json"], text=True)
	data = json.loads(out)
	for peer in data.get("Peer", {}).values():
		if peer.get("HostName") == hostname and peer.get("TailscaleIPs"):
			return peer["TailscaleIPs"][0]
	sys.exit(f"error: tailnet host {hostname!r} not found in peers")


def reconcile_cf(token: str, zone: str, record_name: str, target_ip: str) -> None:
	zones = http("GET", f"https://api.cloudflare.com/client/v4/zones?name={zone}", token)
	if not zones.get("success") or not zones.get("result"):
		sys.exit(f"error: cannot read CF zone {zone}: {zones}")
	zone_id = zones["result"][0]["id"]

	records = http(
		"GET",
		f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records?name={record_name}",
		token,
	)
	if not records.get("success"):
		sys.exit(f"error: cannot read CF records: {records}")

	desired = {"type": "A", "name": record_name, "content": target_ip, "proxied": False, "ttl": 300}

	existing = (records.get("result") or [None])[0]
	if existing and existing["type"] == desired["type"] and existing["content"] == desired["content"]:
		print(f"  ok    CF      {record_name} A {target_ip}")
		return

	if existing:
		resp = http(
			"PUT",
			f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{existing['id']}",
			token,
			desired,
		)
		action = "updated"
	else:
		resp = http(
			"POST", f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records", token, desired
		)
		action = "created"

	if not resp.get("success"):
		sys.exit(f"error: CF {action} failed: {resp}")
	print(f"  {action} CF      {record_name} A {target_ip}")


def reconcile_tailscale(token: str, tailnet: str, zone: str, resolvers: list[str]) -> None:
	current = http(
		"GET", f"https://api.tailscale.com/api/v2/tailnet/{tailnet}/dns/split-dns", token
	)
	if zone in current and current[zone] == resolvers:
		print(f"  ok    TS      split-dns {zone} -> {resolvers}")
		return

	resp = http(
		"PATCH",
		f"https://api.tailscale.com/api/v2/tailnet/{tailnet}/dns/split-dns",
		token,
		{zone: resolvers},
	)
	if zone not in resp:
		sys.exit(f"error: TS split-dns patch failed: {resp}")
	print(f"  updated TS      split-dns {zone} -> {resolvers}")


def main() -> int:
	cf_token = env("CF_API_TOKEN")
	ts_token = env("TS_API_KEY")
	tailnet = env("TS_TAILNET")
	hostname = env("TS_HOSTNAME")
	zone = env("DNS_ZONE")
	record_name = env("DNS_HOSTNAME")
	resolvers = [
		s.strip()
		for s in os.environ.get("SPLIT_DNS_RESOLVERS", "1.1.1.1,1.0.0.1").split(",")
		if s.strip()
	]

	target_ip = find_tailnet_ip(hostname)
	print(f"tailnet IP for {hostname!r}: {target_ip}")
	reconcile_cf(cf_token, zone, record_name, target_ip)
	reconcile_tailscale(ts_token, tailnet, zone, resolvers)
	return 0


if __name__ == "__main__":
	sys.exit(main())
