"""Reproduce the recooldown audit and graphs without altering acquisition code.

Usage: python3 analysis/analyze_recooldown.py
Requires pandas, numpy, matplotlib in the analysis Python environment.
Primary analysis: runs _2 through _6. _1 is used only to audit reference markers.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import html
import json
import platform
import zipfile

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/recooldown/raw'
OUT = ROOT / 'results/recooldown'
OUT.mkdir(parents=True, exist_ok=True)
TZ = ZoneInfo('America/Toronto')
COLORS = {2:'#0072B2', 3:'#D55E00', 4:'#009E73', 5:'#CC79A7', 6:'#6D5AA6'}
plt.rcParams.update({'font.size':10, 'axes.titlesize':12, 'axes.labelsize':10,
                     'figure.titlesize':16, 'axes.spines.top':False,
                     'axes.spines.right':False, 'axes.grid':True,
                     'grid.alpha':0.2, 'savefig.facecolor':'white',
                     'svg.fonttype':'none'})

frames, metadata, inventory, run_stats = [], {}, [], []
for path in sorted(RAW.glob('*.csv')):
    frame = pd.read_csv(path)
    times = pd.to_datetime(frame.timestamp_utc, utc=True)
    meta_path = path.with_suffix('.csv.json')
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    simulated = frame.simulated.astype(str).str.lower().eq('true').any()
    inventory.append({'file':path.name, 'rows':len(frame), 'simulated':bool(simulated),
                      'start_utc':times.iloc[0].isoformat(), 'end_utc':times.iloc[-1].isoformat(),
                      'quality_counts':frame.quality.value_counts(dropna=False).to_dict(),
                      'metadata_status':meta.get('status'), 'metadata_rows':meta.get('rows')})
for run in range(2,7):
    path = RAW / f'run_20261124_{run}.csv'
    frame = pd.read_csv(path)
    assert not frame.simulated.astype(str).str.lower().eq('true').any()
    frame['source_file'] = path.name
    frame['source_run'] = run
    frame['source_row'] = np.arange(len(frame))
    frame['timestamp'] = pd.to_datetime(frame.timestamp_utc, utc=True)
    assert frame.timestamp.is_monotonic_increasing
    assert not frame.timestamp.duplicated().any()
    frame['electrical_valid'] = (frame.quality.eq('ok') &
        frame[['lockin_x_v','lockin_y_v','lockin_magnitude_v','lockin_phase_deg']].notna().all(axis=1))
    metadata[run] = json.loads(path.with_suffix('.csv.json').read_text())
    frames.append(frame)
    dt = frame.timestamp.diff().dt.total_seconds()
    run_stats.append({'run':run, 'file':path.name, 'rows':len(frame),
        'electrical_valid_rows':int(frame.electrical_valid.sum()),
        'start_local':frame.timestamp.iloc[0].tz_convert(TZ).isoformat(),
        'end_local':frame.timestamp.iloc[-1].tz_convert(TZ).isoformat(),
        'span_s':float((frame.timestamp.iloc[-1]-frame.timestamp.iloc[0]).total_seconds()),
        'median_interval_s':float(dt.median()), 'max_interval_s':float(dt.max()),
        'primary_first_mv':float(frame.diode_voltage_mv.iloc[0]),
        'primary_last_mv':float(frame.diode_voltage_mv.iloc[-1]),
        'ch2_first_mv':float(frame.diode_ch2_voltage_mv.iloc[0]),
        'ch2_last_mv':float(frame.diode_ch2_voltage_mv.iloc[-1]),
        'x_first60_median_mv':float(frame.loc[frame.electrical_valid].head(60).lockin_x_v.median()*1000),
        'x_last60_median_mv':float(frame.loc[frame.electrical_valid].tail(60).lockin_x_v.median()*1000),
        'metadata_status':metadata[run].get('status'), 'metadata_rows':metadata[run].get('rows'),
        'termination_error':metadata[run].get('error','')})
all_data = pd.concat(frames, ignore_index=True).sort_values('timestamp')
assert len(all_data)==11201
assert not all_data.timestamp.duplicated().any()
valid = all_data.loc[all_data.electrical_valid].copy()
gaps=[]
for left,right in zip(frames[:-1],frames[1:]):
    seconds=(right.timestamp.iloc[0]-left.timestamp.iloc[-1]).total_seconds()
    gaps.append({'from_run':int(left.source_run.iloc[0]),'to_run':int(right.source_run.iloc[0]),
                 'start_utc':left.timestamp.iloc[-1].isoformat(),
                 'end_utc':right.timestamp.iloc[0].isoformat(),'seconds':seconds})
all_data['lockin_x_mv'] = all_data.lockin_x_v*1000
all_data['lockin_y_mv'] = all_data.lockin_y_v*1000
all_data['electrical_quality_note'] = np.where(all_data.electrical_valid, 'complete_ok_row',
    'partial_error_row_retained_but_excluded_from_electrical_plots')
all_data['base_plate_diode_voltage_mv'] = all_data.diode_voltage_mv
all_data['sample_diode_voltage_mv'] = all_data.diode_ch2_voltage_mv
all_data.drop(columns=['timestamp']).to_csv(OUT/'merged_runs_2_to_6.csv',index=False)
pd.DataFrame(run_stats).to_csv(OUT/'run_summary.csv',index=False)

reference = pd.read_csv(RAW/'run_20261124_1.csv')
reference['timestamp'] = pd.to_datetime(reference.timestamp_utc,utc=True)
events = [json.loads(line) for line in (RAW/'run_20261124_1.csv.events.jsonl').read_text().splitlines()]
reference_stats={}
for name in ['warm','cold']:
    a=pd.Timestamp(next(e['timestamp_utc'] for e in events if e['label']==name+'-start'))
    b=pd.Timestamp(next(e['timestamp_utc'] for e in events if e['label']==name+'-end'))
    selected=reference.loc[reference.timestamp.between(a,b)]
    reference_stats[name]={'start_utc':a.isoformat(),'end_utc':b.isoformat(),
        'n':len(selected),'first_mv':float(selected.diode_voltage_mv.iloc[0]),
        'last_mv':float(selected.diode_voltage_mv.iloc[-1]),
        'mean_mv':float(selected.diode_voltage_mv.mean()),'sd_mv':float(selected.diode_voltage_mv.std())}

peak=all_data.loc[all_data.diode_voltage_mv.idxmax()]
first_x=frames[0].loc[frames[0].electrical_valid].head(60).lockin_x_v.median()
last_x=frames[-1].loc[frames[-1].electrical_valid].tail(60).lockin_x_v.median()
summary={'selection':'run_20261124_2.csv through run_20261124_6.csv',
 'total_rows':len(all_data),'complete_ok_electrical_rows':len(valid),
 'partial_error_rows':int((~all_data.electrical_valid).sum()),
 'first_local':all_data.timestamp.iloc[0].tz_convert(TZ).isoformat(),
 'last_local':all_data.timestamp.iloc[-1].tz_convert(TZ).isoformat(),
 'wall_span_hours':float((all_data.timestamp.iloc[-1]-all_data.timestamp.iloc[0]).total_seconds()/3600),
 'recorded_segment_span_hours':sum(x['span_s'] for x in run_stats)/3600,
 'gaps':gaps,'reference_audit':reference_stats,
 'warm_reference_c_from_note':23.5,'cold_reference_validated':False,
 'primary_voltage_min_mv':float(all_data.diode_voltage_mv.min()),
 'primary_voltage_max_mv':float(peak.diode_voltage_mv),
 'primary_peak_local':peak.timestamp.tz_convert(TZ).isoformat(),
 'channel2_min_mv':float(all_data.diode_ch2_voltage_mv.min()),
 'channel2_max_mv':float(all_data.diode_ch2_voltage_mv.max()),
 'x_first_median_mv':float(first_x*1000),'x_last_median_mv':float(last_x*1000),
 'x_fractional_drop':float(1-last_x/first_x),
 'x_unique_levels_v':sorted(valid.lockin_x_v.unique().tolist()),
 'y_unique_levels_v':sorted(valid.lockin_y_v.unique().tolist()),
 'smallest_observed_x_step_uv':float(np.diff(np.unique(valid.lockin_x_v)).min()*1e6),
 'current_from_files_a':None,'physical_channel_mapping_verified':True, 'channel_mapping_source':'User confirmed channel 1 base plate, channel 2 sample', 'channel_mapping':{'1':'base plate','2':'sample'},
 'limitations':['No independently established cold reference in archive.',
 'User confirmed channel 1 is base plate and channel 2 is sample; legacy CLI sample label refers to channel 1.',
 'No current measurements or sample geometry in files.',
 'No observed zero-voltage state; Tc cannot be extracted from these plots.',
 'Four partial error rows excluded from electrical plots; their valid diode readings retained.',
 'No interpolation across file gaps; timestamps remain absolute.',
 'Metadata for _6 says running and 32 rows; actual CSV has 40 rows, consistent with an unfinished snapshot.'],
 'analysis_environment':{'python':platform.python_version(),'pandas':pd.__version__,
                         'numpy':np.__version__,'matplotlib':matplotlib.__version__},
 'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(RAW.iterdir()) if p.is_file()}}
(OUT/'analysis_summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')

plots=[]
def save(fig,name,caption):
    fig.savefig(OUT/(name+'.png'),dpi=220,bbox_inches='tight')
    fig.savefig(OUT/(name+'.svg'),bbox_inches='tight')
    plt.close(fig)
    plots.append((name,caption))

def format_time(ax):
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M',tz=TZ))
    ax.set_xlabel('24 November 2026, Toronto time (EST)')

def shade_gaps(ax):
    for gap in gaps:
        if gap['seconds']>120:
            ax.axvspan(pd.Timestamp(gap['start_utc']),pd.Timestamp(gap['end_utc']),
                       color='#eeeeee',zorder=0)

def plot_by_run(ax,column,factor=1,electrical=False):
    for frame in frames:
        subset=frame.loc[frame.electrical_valid] if electrical else frame
        run=int(frame.source_run.iloc[0])
        ax.plot(subset.timestamp,subset[column]*factor,color=COLORS[run],lw=1.25,
                marker='o' if run in (4,6) else None,ms=2,label=f'Run {run}')
    shade_gaps(ax)

fig,axes=plt.subplots(3,1,figsize=(11.5,9),sharex=True,layout='constrained')
fig.suptitle('Recooldown: recorded diode and electrical signals')
plot_by_run(axes[0],'diode_voltage_mv'); axes[0].set_ylabel('Base plate diode, ch. 1 (mV)')
axes[0].legend(title='Run suffix',ncol=5,loc='lower right',frameon=True)
axes[0].annotate('Grey band: no recorded data\n75.7-minute gap',
    xy=(pd.Timestamp(gaps[1]['start_utc'])+(pd.Timestamp(gaps[1]['end_utc'])-pd.Timestamp(gaps[1]['start_utc']))/2,960),
    ha='center',fontsize=9)
plot_by_run(axes[1],'diode_ch2_voltage_mv');axes[1].set_ylabel('Sample diode, ch. 2 (mV)')
plot_by_run(axes[2],'lockin_x_v',1000,True);axes[2].set_ylabel('Lock-in X (mV)')
axes[2].plot(valid.timestamp,valid.lockin_y_v*1000,'.',color='#444444',ms=1,label='Y = 0.05 mV')
axes[2].legend(loc='upper right',ncol=3)
for ax in axes:
 ax.axvline(pd.Timestamp('2026-11-24T16:28:17.443888+00:00'),color='#666666',ls=':',lw=1)
axes[1].text(pd.Timestamp('2026-11-24T16:28:17.443888+00:00'),615,
             ' Vacuum redone (event note)',rotation=90,va='bottom',fontsize=8)
format_time(axes[-1])
save(fig,'01_time_overview','Runs _2–_6, with actual elapsed gaps. Channel 1 = base plate; channel 2 = sample (user confirmed). Diodes are raw mV, not calibrated temperatures. Four partial electrical rows are excluded from X/Y traces.')

fig,axes=plt.subplots(1,2,figsize=(12,5),layout='constrained',sharey=True)
fig.suptitle('Electrical response versus each diode voltage')
for ax,column,label in zip(axes,['diode_voltage_mv','diode_ch2_voltage_mv'],['Base plate diode, ch. 1 (mV)','Sample diode, ch. 2 (mV)']):
 for frame in frames:
  f=frame.loc[frame.electrical_valid];run=int(frame.source_run.iloc[0])
  ax.scatter(f[column],f.lockin_x_v*1000,s=5,color=COLORS[run],alpha=.35,rasterized=True,label=f'Run {run}')
 ax.set_xlabel(label);ax.legend(title='Run suffix',ncol=3,markerscale=2)
axes[0].set_ylabel('Lock-in X (mV)')
axes[0].text(.03,.03,'Discrete 0.05 mV levels\nNo confirmed zero-voltage state',transform=axes[0].transAxes,fontsize=9)
save(fig,'02_voltage_response','The horizontal axes deliberately remain diode voltage. Channel 1 is the base plate and channel 2 is the sample (user confirmed). Cold calibration and current are not established by these files.')

fig,axes=plt.subplots(2,1,figsize=(11.5,7.5),sharex=True,layout='constrained')
fig.suptitle('Near the base plate plateau: voltage keeps changing slowly')
cut=pd.Timestamp('2026-11-24T17:00:00+00:00')
for frame in frames:
 run=int(frame.source_run.iloc[0]);f=frame.loc[frame.timestamp>=cut]
 if f.empty:continue
 axes[0].plot(f.timestamp,f.diode_voltage_mv,color=COLORS[run],lw=1.1,label=f'Run {run}')
 good=f.loc[f.electrical_valid]
 axes[1].plot(good.timestamp,good.lockin_x_v*1000,color=COLORS[run],lw=1.1)
for ax in axes:shade_gaps(ax)
axes[0].set_ylabel('Base plate diode, ch. 1 (mV)');axes[0].legend(ncol=4,title='Run suffix')
axes[1].set_ylabel('Lock-in X (mV)');format_time(axes[1])
axes[0].annotate(f"Maximum {peak.diode_voltage_mv:.3f} mV\n{peak.timestamp.tz_convert(TZ):%H:%M:%S} EST",
 xy=(peak.timestamp,peak.diode_voltage_mv),xytext=(15,-45),textcoords='offset points',
 arrowprops={'arrowstyle':'->','color':'#555555'},fontsize=9)
save(fig,'03_plateau_detail','After the base plate diode peaks near 981.166 mV, it declines slightly; electrical voltage continues falling. This is not a resolved superconducting transition or a calibrated heating curve.')

fig,axes=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
fig.suptitle('Calibration-marker audit (supporting file _1)')
for ax,name,title in zip(axes,['warm','cold'],['Warm marker: 23.5 °C recorded','Cold marker: still changing, not validated at 77 K']):
 stat=reference_stats[name];a=pd.Timestamp(stat['start_utc']);b=pd.Timestamp(stat['end_utc'])
 f=reference.loc[reference.timestamp.between(a,b)]
 ax.plot((f.timestamp-a).dt.total_seconds(),f.diode_voltage_mv,color='#0072B2' if name=='warm' else '#D55E00',lw=1.5,marker='.' if name=='warm' else None)
 ax.set_title(title,fontsize=11);ax.set_xlabel('Seconds from interval marker');ax.set_ylabel('Base plate diode, ch. 1 (mV)')
 ax.ticklabel_format(axis='y',style='plain',useOffset=False)
 ax.text(.48 if name=='warm' else .04,.94,f"n = {stat['n']}\nmean = {stat['mean_mv']:.3f} mV\nSD = {stat['sd_mv']:.3f} mV",transform=ax.transAxes,va='top',fontsize=9)
save(fig,'04_calibration_audit','The warm interval is short but stable. During the marked cold interval the diode changes by 68.365 mV; it cannot be accepted as a stable 77 K point from these records.')

# Conditional illustration only: the user's earlier bench current was 79.8 mA.
# It was NOT recorded by the logger and is not confirmed constant during these runs.
assumed_current=.0798
fig,ax=plt.subplots(figsize=(11.5,4.8),layout='constrained')
fig.suptitle('Conditional resistance estimate: assumes constant 79.8 mA RMS')
for frame in frames:
 f=frame.loc[frame.electrical_valid];run=int(frame.source_run.iloc[0])
 ax.plot(f.timestamp,f.lockin_x_v/assumed_current*1000,color=COLORS[run],lw=1.2,label=f'Run {run}')
shade_gaps(ax);format_time(ax);ax.set_ylabel('X / assumed current (mΩ)');ax.legend(ncol=5,title='Run suffix')
ax.text(.02,.06,'Illustrative only: current was not logged or confirmed constant.\nRequires correct reference phase, gain and wiring.',transform=ax.transAxes,fontsize=9,
        bbox={'facecolor':'white','alpha':.9,'edgecolor':'#cccccc'})
save(fig,'05_conditional_resistance','Assuming the earlier reported 79.8 mA remained constant, initial/final median X correspond to about 9.40/4.39 mΩ. This is explicitly conditional, not a measured resistance calibration.')

# User-requested provisional calibration: highest recorded ch1 voltage is assumed
# to represent the nominal 77 K LN2 reference. This is not a sensor-2 calibration.
warm_k, cold_k = 23.5 + 273.15, 77.0
warm_mv, cold_mv = reference_stats['warm']['mean_mv'], float(peak.diode_voltage_mv)
slope = (cold_mv - warm_mv) / (warm_k - cold_k)  # positive mV/K in V = c1 - c2*T
intercept = warm_mv + slope * warm_k
calibrated = all_data.copy()
in_range = calibrated.diode_voltage_mv.between(warm_mv, cold_mv)
calibrated['base_plate_temperature_provisional_k'] = np.where(
    in_range, (intercept - calibrated.diode_voltage_mv) / slope, np.nan)
calibrated['base_plate_calibration_quality'] = np.where(in_range,
    'provisional_linear_assumed_ln2_equilibrium', 'outside_reference_range')
calibrated.drop(columns=['timestamp']).to_csv(OUT/'base_plate_calibrated_runs_2_to_6.csv',index=False)
near_peak = all_data.loc[all_data.timestamp.between(peak.timestamp-pd.Timedelta(seconds=30),
                                                 peak.timestamp+pd.Timedelta(seconds=30))]
calibration = {
    'channel':1, 'sensor':'base plate', 'status':'provisional', 'model':'linear',
    'equation':'V_mV = c1_mV - c2_mV_per_K * T_K',
    'c1_mv':intercept, 'c2_mv_per_k':slope, 'c3_mv':0,
    'warm':dict(reference_stats['warm'], temperature_k=warm_k, temperature_c=23.5,
                source_file='run_20261124_1.csv'),
    'cold':{'temperature_k':cold_k,'voltage_mv':cold_mv,
            'source_file':peak.source_file, 'source_row':int(peak.source_row),
            'timestamp_utc':peak.timestamp.isoformat(),
            'selection':'highest recorded channel-1 voltage, per user instruction',
            'assumption':'base plate at nominal LN2 boiling temperature, 77 K',
            'nearby_60s_count':len(near_peak),
            'nearby_60s_mean_mv':float(near_peak.diode_voltage_mv.mean()),
            'nearby_60s_sd_mv':float(near_peak.diode_voltage_mv.std())},
    'temperature_first_k':float(calibrated.base_plate_temperature_provisional_k.iloc[0]),
    'temperature_last_k':float(calibrated.base_plate_temperature_provisional_k.iloc[-1]),
    'limitations':['Highest voltage is a user-selected cold-reference assumption, not independent equilibrium verification.',
                   'Linear two-point interpolation does not validate intermediate diode temperatures.',
                   'No pressure correction or physical temperature uncertainty is established.',
                   'Channel 2 (sample) is NOT calibrated by this curve.',
                   'Base plate temperature is not automatically sample temperature.',
                   'No extrapolation, current calibration or transition-temperature extraction.']}
(OUT/'base_plate_calibration.json').write_text(json.dumps(calibration,indent=2)+'\n')
summary['provisional_base_plate_calibration'] = calibration
(OUT/'analysis_summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')

fig,axes=plt.subplots(2,1,figsize=(11.5,7),sharex=True,layout='constrained')
fig.suptitle('Provisional base plate temperature and sample voltage\nCh. 1: 433.188 mV = 296.65 K; 981.166 mV = nominal 77 K. Ch. 2 not shown.',fontsize=13)
for run,frame in calibrated.groupby('source_run'):
 axes[0].plot(frame.timestamp,frame.base_plate_temperature_provisional_k,
              color=COLORS[run],lw=1.2,label=f'Run {run}')
 good=frame.loc[frame.electrical_valid]
 axes[1].plot(good.timestamp,good.lockin_x_v*1000,color=COLORS[run],lw=1.2)
for ax in axes: shade_gaps(ax)
axes[0].set_ylabel('Base plate temperature (K)\nprovisional linear calibration')
axes[0].axhline(77,color='#555555',ls='--',lw=1)
axes[0].legend(ncol=5,loc='upper right')
axes[1].set_ylabel('Lock-in X (mV)');format_time(axes[1])
save(fig,'06_base_plate_temperature','User-requested provisional calibration of channel 1 only. The highest recorded voltage is assigned nominal 77 K. Gaps remain blank; this is not the sample temperature.')

fig,ax=plt.subplots(figsize=(10,5),layout='constrained')
fig.suptitle('Sample voltage versus provisional BASE PLATE temperature')
for run,frame in calibrated.groupby('source_run'):
 good=frame.loc[frame.electrical_valid]
 ax.scatter(good.base_plate_temperature_provisional_k,good.lockin_x_v*1000,
            color=COLORS[run],s=5,alpha=.35,rasterized=True,label=f'Run {run}')
ax.set_xlabel('Base plate temperature (K), provisional linear calibration')
ax.set_ylabel('Lock-in X (mV)');ax.legend(ncol=3,loc='lower right',markerscale=2)
ax.text(.03,.04,'Base plate axis is not calibrated sample temperature.\nNo transition temperature or zero-resistance state established.',
        transform=ax.transAxes,fontsize=9)
save(fig,'07_voltage_vs_base_plate_temperature','Electrical voltage versus channel-1 base plate temperature; the separate provisional sample estimates are not used on this base plate axis. The two-point linear model is provisional, and actual current was not logged.')

# Compact report with source provenance and no hidden calibration assumptions.
rows=''.join(f"<tr><td>_{s['run']}</td><td>{s['rows']:,}</td><td>{s['span_s']/60:.2f}</td><td>{s['start_local'][11:19]}</td><td>{s['end_local'][11:19]}</td><td>{html.escape(s['metadata_status'])}</td></tr>" for s in run_stats)
sensor_update = ''
new_sensor_export = OUT/'both_sensors_calibrated_runs_2_to_6.csv'
if new_sensor_export.exists():
 sensor_update = ('<section><h2>Subsequent provisional sample calibration</h2>'
  '<p>The logger now labels base_plate (ch1) and sample (ch2) explicitly. A separate provisional sample curve uses '
  'user-reported 28.08 mV at assumed 23.5 °C and approximately 619 mV at nominal 77 K. '
  'These references are approximate, not independently verified. The existing figures below use the base plate curve only.</p>'
  '<p><a href="both_sensors_calibrated_runs_2_to_6.csv">Both-sensor temperature export</a> · '
  '<a href="both_sensors_calibrated_runs_2_to_6.csv.calibration.json">Profile, assumptions and quality counts</a></p>'
  '<p>Only 133 of the 11,201 archived sample readings lie inside the provisional voltage range; '
  '11,068 are flagged outside_reference_range with blank derived temperatures and preserved raw voltages. '
  'No below-77 K temperature is inferred by extrapolating those readings.</p></section>')
sections=''.join(f'<section><img src="{name}.png" alt="{html.escape(caption)}"><p>{html.escape(caption)}</p><p><a href="{name}.svg">Vector SVG</a></p></section>' for name,caption in plots)
report=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Recooldown analysis</title>
<style>body{{max-width:1100px;margin:35px auto;padding:0 22px;font:17px/1.55 system-ui;color:#17212b;background:#fafafa}}h1,h2{{line-height:1.2}}section{{background:white;border:1px solid #ddd;border-radius:8px;padding:20px;margin:24px 0}}img{{width:100%;height:auto}}table{{border-collapse:collapse;width:100%;font-size:15px}}td,th{{padding:9px;border-bottom:1px solid #ddd;text-align:left}}a{{color:#0067a3}}.note{{border-left:4px solid #d55e00;padding:10px 20px;background:#fff6ed}}li{{margin:8px 0}}</style>
<h1>Recooldown analysis</h1><p>Runs _2–_6, 24 November 2026. All graph times are Toronto EST (UTC−5).</p>
<p><strong>{len(all_data):,} rows</strong> span {summary['wall_span_hours']:.2f} hours of wall time, with {summary['recorded_segment_span_hours']:.2f} hours inside the recorded segments. {len(valid):,} rows contain complete electrical measurements with quality=ok.</p>
<div class="note"><strong>A provisional base plate calibration is now provided at the user’s request.</strong> Channel 1 uses the measured 23.5 °C warm reference and the highest recorded voltage assigned nominal 77 K. LN2 equilibrium is assumed rather than independently verified. No current was logged. Channel 1 is the base plate; channel 2 is the sample, as confirmed by the user. The warm-reference audit below applies to channel 1 only. No transition temperature is inferred.</div>
{sensor_update}<h2>Main findings</h2><ul>
<li>Base plate diode voltage rises from 940.447 mV to a maximum of 981.166 mV, then settles near 980.1 mV. Increasing diode voltage is consistent with cooling; the subsequent small decline is consistent with slight warming if sensor excitation remained stable.</li>
<li>Initial/final median X falls from {first_x*1000:.2f} to {last_x*1000:.2f} mV, a {summary['x_fractional_drop']*100:.1f}% decrease. Voltage alone cannot distinguish resistance changes from current or wiring changes.</li>
<li>There is no observed zero-voltage state. The electrical output occupies 50 µV levels; Y is 50 µV in every complete row. The metadata records 500 mV sensitivity, so resolution is coarse for this signal. No quantitative noise floor or zero-resistance bound is established.</li>
<li>The sample diode (channel 2) ranges from {summary['channel2_min_mv']:.3f} to {summary['channel2_max_mv']:.3f} mV and fluctuates strongly relative to the base plate diode. Do not assume both channels reached the same known temperature.</li>
<li>Four rows end with errors. The longest gap is {max(x['seconds'] for x in gaps)/60:.2f} minutes between _3 and _4. No line is interpolated across file boundaries. Errors occurred after ~1252, 9500 and only 12 rows, so the failures are not evidence of a fixed 10,000-second limit.</li>
<li>_6 contains 40 actual CSV rows, while its metadata still says running and 32 rows. Analyze the CSV as a captured segment, not as proof of a cleanly finished acquisition.</li></ul>
<h2>Calibration audit</h2><p>Supporting file _1 has a 13-reading channel-1 (base plate) warm interval at 23.5 °C, mean {reference_stats['warm']['mean_mv']:.6f} mV and sample SD {reference_stats['warm']['sd_mv']:.6f} mV. Its cold markers enclose 379 readings rising from 769.892 to 838.257 mV (mean {reference_stats['cold']['mean_mv']:.3f} mV, SD {reference_stats['cold']['sd_mv']:.3f} mV), not a plateau. Earlier historical 22.2 °C and invalidated 26.2 °C references are not substituted. Even the later ~980.1 mV plateau is not automatically assigned 77 K without physical confirmation.</p>
<h2>Provisional base plate calibration</h2><p>At the user’s request, the highest recorded base plate voltage, {cold_mv:.3f} mV, is assigned nominal 77 K. With the warm point {warm_mv:.6f} mV at {warm_k:.2f} K, the linear curve is V_mV = {intercept:.6f} − {slope:.9f} × T_K. Channel 1 spans approximately {calibration["temperature_first_k"]:.2f} K initially to a minimum of 77 K, ending at {calibration["temperature_last_k"]:.2f} K. This is a provisional base plate temperature, not a calibrated sample temperature. The approximate remembered 990 mV is not substituted for the recorded 981.166 mV.</p><p><a href="base_plate_calibrated_runs_2_to_6.csv">Data with provisional base plate temperatures</a> · <a href="base_plate_calibration.json">Calibration coefficients, references and limitations</a></p><h2>Segments</h2><table><tr><th>Run</th><th>Rows</th><th>Span (min)</th><th>Start EST</th><th>End EST</th><th>Metadata status</th></tr>{rows}</table>
{sections}
<h2>Method and limitations</h2><p>Raw inputs remain unchanged. All _2–_6 rows are retained in the merged CSV with source filename and row. Electrical plots use only complete quality=ok rows. Diode plots retain the valid diode values in partial error rows. No smoothing, imputation or gap interpolation is applied. Figures 1–5 preserve raw voltage axes; figures 6–7 apply the separately documented provisional base plate calibration only. _1 is used only for the supporting reference audit; startup, simulation and earlier setup measurements are excluded from the main graphs. No recorded warming branch is manufactured.</p>
<p>To obtain R(T) for the sample (channel 2), establish actual current versus time, phase/gain/wiring, and independent warm/cold reference temperatures for each sensor. With only two reference temperatures, a three-parameter logarithmic calibration requires one independently fixed coefficient.</p>
<p>Files: <a href="merged_runs_2_to_6.csv">Merged data with provenance</a> · <a href="run_summary.csv">Run summary</a> · <a href="analysis_summary.json">Numerical audit, environment and source hashes</a>. Sources: recooldown.zip supplied by user (SHA256 ab2abb4d30cbfaa118ea09e312bfc87aa3ceb167b2e27c1b9b460fd617b4c998). Reproduce from project root: <code>python3 analysis/analyze_recooldown.py</code>.</p></html>'''
(OUT/'report.html').write_text(report,encoding='utf-8')
with zipfile.ZipFile(OUT/'recooldown_graphs_and_analysis.zip','w',zipfile.ZIP_DEFLATED) as bundle:
 for path in sorted(OUT.iterdir()):
  if path.is_file() and path.suffix!='.zip': bundle.write(path,arcname=path.name)
print(json.dumps({key:summary[key] for key in ['total_rows','complete_ok_electrical_rows','wall_span_hours','recorded_segment_span_hours','x_fractional_drop','primary_peak_local']},indent=2))
print('Saved report, seven PNG/SVG figures, derived CSVs, JSON audit and ZIP:',OUT)
