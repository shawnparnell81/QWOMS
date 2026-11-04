"""Prepare local deployment secrets; does not provision hosting, DNS or TLS certificates."""
import argparse
import ipaddress
from pathlib import Path
import re
import secrets

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--host', required=True, help='Approved demo DNS hostname, no scheme/path')
parser.add_argument('--allowed-cidr', action='append', required=True, help='Approved viewer IP/CIDR; repeatable')
parser.add_argument('--output', default='.env.demo')
args=parser.parse_args()
if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?',args.host) or '.' not in args.host or '..' in args.host:
    parser.error('Use a DNS hostname without scheme, port or path')
networks=[ipaddress.ip_network(c,strict=False) for c in args.allowed_cidr]
if any(n.prefixlen==0 for n in networks):
    parser.error('Private demo requires restricted viewer networks, not an all-address range')
path=Path(args.output)
with path.open('x') as out:
    path.chmod(0o600)
    out.write('QWOMS_IMAGE_TAG=local\n')
    out.write('QWOMS_DEMO_HOST='+args.host+'\n')
    out.write('QWOMS_DEMO_ALLOWED_CIDRS="'+' '.join(str(n) for n in networks)+'"\n')
    out.write('QWOMS_DB_PASSWORD='+secrets.token_hex(32)+'\n')
    out.write('QWOMS_SECRET_KEY='+secrets.token_hex(48)+'\n')
print('Prepared private local environment file. No services provisioned; keep it out of Git.')
