"""Plot recent GitHub backups on the analysis computer; optionally publish the PNG."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sensor_calibration import load_profile, named_reading
from github_backup import github_api, GitHubError, DEFAULT_REPO, BRANCH

OUT = ROOT / 'output/live-monitor'
OUT.mkdir(parents=True, exist_ok=True)

def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])

def publish_plot(key, name):
    """Only publish once per snapshot/profile; failed uploads are retried."""
    state = OUT/'published.json'
    if state.exists() and json.loads(state.read_text()).get('key') == key:
        return
    endpoint = f'repos/{DEFAULT_REPO}/contents/live/latest.png'
    payload = {'message': f'Update acquisition graph for {name}', 'branch': BRANCH,
               'content': base64.b64encode((OUT/'latest.png').read_bytes()).decode('ascii')}
    try:
        payload['sha'] = github_api(endpoint + '?ref=main')['sha']
    except GitHubError as exc:
        if 'HTTP 404' not in str(exc):
            raise
    result = github_api(endpoint, 'PUT', payload)
    state.write_text(json.dumps({'key':key,'commit':result['commit']['sha']},indent=2))
    print(f'Published https://github.com/{DEFAULT_REPO}/blob/main/live/latest.png',flush=True)

def refresh(publish=False):
    git('fetch', 'origin', 'main')
    revision = git('rev-parse', 'origin/main').decode().strip()
    candidates = []
    for path in git('ls-tree', '-r', '--name-only', revision, 'live/').decode().splitlines():
        if not path.endswith('/snapshot.zip'):
            continue
        blob = git('show', revision + ':' + path)
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            name = next(n for n in archive.namelist() if n.endswith('.csv'))
            metadata = json.loads(archive.read(name + '.json'))
            if metadata.get('simulated') or name.startswith('SIMULATED'):
                continue
            data = pd.read_csv(io.BytesIO(archive.read(name)))
            if data.empty:
                continue
            dates = pd.to_datetime(data.timestamp_utc, utc=True, format='mixed')
            candidates.append((dates.iloc[-1], path, name, metadata, data, dates, blob))
    if not candidates:
        raise RuntimeError('No real acquisition backups found.')
    latest, path, name, metadata, data, dates, blob = max(candidates, key=lambda c: c[0])
    profile = load_profile()
    key = hashlib.sha256(blob + json.dumps(profile,sort_keys=True).encode() + Path(__file__).read_bytes()).hexdigest()
    # Graph commits themselves do not change the source snapshot.
    summary_path = OUT/'latest_summary.json'
    if summary_path.exists() and (OUT/'latest.png').exists():
        previous = json.loads(summary_path.read_text())
        if previous.get('plot_key') == key:
            if publish: publish_plot(key, name)
            return
    primary = metadata['arguments']['channel']
    for sensor, spec in profile['sensors'].items():
        channel = spec['channel']
        column = 'diode_voltage_mv' if channel == primary else f'diode_ch{channel}_voltage_mv'
        volts = data[column] if column in data else pd.Series(np.nan, index=data.index)
        data[sensor+'_plot_mv'] = volts
        estimates = [named_reading(profile, channel, v) for v in volts]
        data[sensor+'_plot_k'] = pd.to_numeric(pd.Series([r[sensor+'_temperature_calibrated_k'] for r in estimates]), errors='coerce')
        data[sensor+'_plot_quality'] = [r[sensor+'_calibration_quality'] for r in estimates]
    minutes = (dates-dates.iloc[0]).dt.total_seconds()/60
    # Do not bridge interrupted sampling gaps.
    breaks = minutes.diff().gt(5/60)
    fig, axes = plt.subplots(3, 1, figsize=(11,9), sharex=True, layout='constrained')
    colors = {'base_plate':'#0072B2', 'sample':'#D55E00'}
    for sensor in colors:
        label = sensor.replace('_',' ').title()
        for ax, suffix in [(axes[0], '_plot_k'), (axes[1], '_plot_mv')]:
            y = data[sensor+suffix].mask(breaks)
            ax.plot(minutes, y, color=colors[sensor], label=label, marker='.' if len(data)<10 else None)
    axes[0].set_ylabel('Temperature (K)')
    axes[0].legend()
    axes[1].set_ylabel('Raw diode voltage (mV)')
    axes[1].legend()
    valid = data.quality.eq('ok') if 'quality' in data else pd.Series(True,index=data.index)
    for column, label, color in [('lockin_x_v','X','#009E73'),('lockin_y_v','Y','#CC79A7')]:
        if column in data:
            axes[2].plot(minutes, (data[column]*1000).where(valid & ~breaks), label=label,color=color)
    axes[2].set_ylabel('Lock-in voltage (mV)')
    axes[2].set_xlabel('Minutes since first recorded sample')
    axes[2].legend()
    for ax in axes: ax.grid(alpha=.25)
    local = latest.tz_convert('America/Toronto')
    fig.suptitle(f'Latest acquisition backup · {local:%Y-%m-%d %H:%M:%S %Z}\n{len(data):,} rows · {metadata.get("status","unknown")} · two-point temperature estimates (may extrapolate)',fontsize=13)
    fig.savefig(OUT/'latest.png',dpi=180)
    plt.close(fig)
    (OUT/'latest_snapshot.zip').write_bytes(blob)
    data.to_csv(OUT/'latest_readings.csv',index=False)
    report = {'plot_key':key,'commit':revision,'source':path,'file':name,'rows':len(data),'last_reading':latest.isoformat(),'status':metadata.get('status'),'minutes':float(minutes.iloc[-1]),'calibration':profile['id']}
    (OUT/'latest_summary.json').write_text(json.dumps(report,indent=2))
    (OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="60"><title>Latest acquisition</title><style>body{font:18px system-ui;max-width:1100px;margin:30px auto}img{width:100%}</style><h1>Latest GitHub acquisition backup</h1><p>Read-only plot of the most recent real run. Temperature curves are provisional; refresh the Python downloader to obtain newer data.</p><img src="latest.png"><p><a href="latest_readings.csv">CSV</a> · <a href="latest_snapshot.zip">Original backup</a></p>')
    print(json.dumps(report))
    print(data[['base_plate_plot_k','sample_plot_k','lockin_x_v']].iloc[[0,-1]].to_string(index=False))
    print(OUT/'index.html',flush=True)
    if publish: publish_plot(key, name)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch', action='store_true', help='Refresh from GitHub every 60 seconds until Ctrl-C')
    parser.add_argument('--publish', action='store_true', help='Upload latest graph to main/live/latest.png')
    args = parser.parse_args()
    while True:
        try:
            refresh(args.publish)
        except Exception as exc:
            if not args.watch: raise
            print(f'Refresh failed: {exc}; retaining last plot',file=sys.stderr,flush=True)
        if not args.watch: break
        time.sleep(60)
