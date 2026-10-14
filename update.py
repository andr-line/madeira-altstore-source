#!/usr/bin/env python3
"""Generate/update an AltStore Classic source from official Madeira releases."""
import json
import os
import plistlib
import re
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

API = 'https://api.github.com/repos/willfaust/Madeira/releases?per_page=20'
OUT = Path('source.json')
HEADERS = {'User-Agent': 'madeira-altstore-source', 'Accept': 'application/vnd.github+json'}


def fetch_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=40) as response:
        return json.load(response)


def ipa_details(filename):
    with zipfile.ZipFile(filename) as archive:
        names = archive.namelist()
        apps = [x for x in names if re.fullmatch(r'Payload/[^/]+\.app/Info\.plist', x)]
        if len(apps) != 1:
            raise ValueError(f'Expected one main app, found {len(apps)}')
        main = apps[0]
        prefix = main.rsplit('/', 1)[0] + '/'
        info = plistlib.loads(archive.read(main))
        bundle_id = info['CFBundleIdentifier']
        version = str(info['CFBundleShortVersionString'])
        build = str(info['CFBundleVersion'])
        min_os = str(info.get('MinimumOSVersion', '26.0'))
        privacy = {}
        entitlements = set()
        infos = [n for n in names if n == main or re.fullmatch(r'Payload/[^/]+\.app/PlugIns/[^/]+\.appex/Info\.plist', n)]
        with tempfile.TemporaryDirectory() as tmp:
            for plist_name in infos:
                part_info = plistlib.loads(archive.read(plist_name))
                for key, value in part_info.items():
                    if key.endswith('UsageDescription') and isinstance(value, str):
                        privacy[key] = value
                binary = plist_name.rsplit('/', 1)[0] + '/' + part_info['CFBundleExecutable']
                if binary not in names:
                    raise ValueError(f'Missing executable in IPA: {binary}')
                target = Path(tmp) / f'bin{len(entitlements)}_{len(privacy)}_{len(plist_name)}'
                target.write_bytes(archive.read(binary))
                # Apple's codesign reads entitlements from the embedded Mach-O signature.
                proc = subprocess.run(['codesign', '-d', '--entitlements', '-', str(target)],
                                      capture_output=True)
                if proc.returncode != 0:
                    raise RuntimeError(f'Cannot inspect entitlements of {binary}: {proc.stderr.decode(errors="replace")}')
                raw = proc.stdout
                if raw.strip():
                    parsed = plistlib.loads(raw)
                    entitlements.update(k for k in parsed if k not in {'application-identifier', 'com.apple.developer.team-identifier'})
        return bundle_id, version, build, min_os, {'entitlements': sorted(entitlements), 'privacy': privacy}


def main():
    releases = fetch_json(API)
    releases = [r for r in releases if not r['draft'] and not r['prerelease']]
    if not releases:
        raise RuntimeError('No stable Madeira releases found')
    match = None
    for release in releases:
        assets = [a for a in release['assets'] if a['name'].lower().endswith('.ipa')]
        if assets:
            match = release, assets[0]
            break
    if match is None:
        raise RuntimeError('No release has an IPA asset')
    release, asset = match
    previous = json.loads(OUT.read_text()) if OUT.exists() else None
    versions = previous['apps'][0]['versions'] if previous and previous.get('apps') else []
    url = asset['browser_download_url']
    if any(v['downloadURL'] == url for v in versions):
        print('Latest IPA already in source; nothing to change')
        return

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'Madeira.ipa'
        print(f'Downloading {asset["name"]} ({asset["size"]} bytes)')
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=120) as response, path.open('wb') as output:
            while block := response.read(1024 * 1024):
                output.write(block)
        if path.stat().st_size != asset['size']:
            raise RuntimeError('IPA size mismatch')
        bundle_id, version, build, min_os, permissions = ipa_details(path)

    if previous and previous['apps'] and previous['apps'][0]['bundleIdentifier'] != bundle_id:
        raise RuntimeError('Bundle identifier changed; manual review required')
    new = {
        'version': version,
        'buildVersion': build,
        'date': release['published_at'],
        'localizedDescription': (release.get('body') or 'New Madeira release')[:10000],
        'downloadURL': url,
        'size': asset['size'],
        'minOSVersion': min_os,
    }
    if any(v['version'] == version and v.get('buildVersion') == build for v in versions):
        raise RuntimeError('Different IPA URL with identical app version/build; review manually')
    # This is one app whose permissions may evolve. Always reflect the newest IPA.
    app = {
        'name': 'Madeira',
        'bundleIdentifier': bundle_id,
        'developerName': 'willfaust',
        'subtitle': 'Run Windows PC games on iPhone',
        'localizedDescription': 'Unofficial AltStore listing of Madeira. IPAs are downloaded directly from the official willfaust/Madeira GitHub releases.',
        'iconURL': 'https://github.com/willfaust.png',
        'category': 'games',
        'versions': [new] + versions,
        'appPermissions': permissions,
    }
    source = {
        'name': 'Madeira (Unofficial)',
        'subtitle': 'Automatic updates from the official Madeira GitHub releases',
        'description': 'Unofficial AltStore Classic source. Not affiliated with the Madeira developer.',
        'website': 'https://github.com/willfaust/Madeira',
        'apps': [app],
        'news': [],
    }
    OUT.write_text(json.dumps(source, ensure_ascii=False, indent=2) + '\n')
    print(f'Updated source: {version} ({build}) — {bundle_id}')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
