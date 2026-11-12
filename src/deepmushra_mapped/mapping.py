"""Frozen, bounded parameter-to-stereo-quality priors and inverse requests."""
import json
from pathlib import Path
import numpy as np
from deepmushra_data.config import file_checksum

TABLE_PATH = Path(__file__).with_name("mapping_table.json")

def load_table():
    table=json.loads(TABLE_PATH.read_text())
    for a,c in table["artifacts"].items():
        x=np.asarray(c["x"]);y=np.asarray(c["quality_mean"])
        if len(x)<2 or np.any(np.diff(x)<=0) or not np.isfinite(x).all() or not np.isfinite(y).all():
            raise ValueError("Invalid mapping table")
        if not (np.all(np.diff(y)>=0) or np.all(np.diff(y)<=0)):
            raise ValueError("Nonmonotonic quality table")
    return table

def parameter_for_quality(artifact,quality):
    table=load_table()
    if artifact not in table["artifacts"]:raise ValueError("Only LP/SH/UN/QN are allowed; PE/TM held out")
    if isinstance(quality,bool) or not isinstance(quality,(int,float)) or not np.isfinite(quality):raise ValueError("Quality must be finite")
    c=table["artifacts"][artifact];x=np.array(c["x"]);y=np.array(c["quality_mean"])
    if not min(y)<=quality<=max(y):raise ValueError(f"{artifact} quality request outside supported [{min(y):.2f},{max(y):.2f}]")
    if np.any(np.diff(y)==0):
        return _plateau_inverse(x, y, quality)
    if y[0]>y[-1]:x=x[::-1];y=y[::-1]
    return float(np.interp(quality,y,x))

def estimate_quality(artifact,parameter):
    table=load_table()
    if artifact not in table["artifacts"]:raise ValueError("Only LP/SH/UN/QN are allowed; PE/TM held out")
    if isinstance(parameter,bool) or not isinstance(parameter,(int,float)) or not np.isfinite(parameter):raise ValueError("Parameter must be finite")
    c=table["artifacts"][artifact];x=c["x"]
    supported=x[0]<=parameter<=x[-1]
    value=float(np.interp(parameter,x,c["quality_mean"])) if supported else None
    category=["Bad","Poor","Fair","Good","Excellent"][min(int(value//20),4)] if value is not None else None
    band=[float(np.interp(parameter,x,[v[i] for v in c["conditional_listener_weight_95_bands"]])) for i in (0,1)] if supported else None
    return {"mapping_id":table["version"]+"/"+artifact,"table_sha256":file_checksum(TABLE_PATH),
        "reference_group":c["reference_group"],"parameter_axis":c["axis"],"parameter_value":float(parameter),
        "support_status":"inside" if supported else "outside_no_extrapolation",
        "status":"odaq_informed_provisional_transfer" if supported else "unsupported",
        "estimated_quality_mean":value,"estimated_quality_category":category,
        "estimated_quality_loss_proxy":100-value if value is not None else None,
        "conditional_reference_listener_weight_95_band":band,
        "band_interpretation":"conditional stereo-reference band; linearly interpolated between knots; not a mono/synthetic population CI",
        "calibration_listeners":c["calibration_listeners"],"reference_sources":c["reference_sources"],
        "mono_transfer_validated":False,"operator_transfer_validated":False,"synthetic_transfer_interval_95":None,
        "human_mushra_score":None,"assumptions":table["assumptions"]}


def _plateau_inverse(x, y, quality):
    """Bounded monotone piecewise-linear inverse; exact ties choose lowest parameter.

    Current frozen curves are strictly monotone and retain their existing np.interp
    path. This tie policy is only used if a supported monotone table has a plateau.
    """
    x = np.asarray(x, dtype=float); y = np.asarray(y, dtype=float)
    if not min(y) <= quality <= max(y):
        raise ValueError("Quality outside supported range")
    exact = x[y == quality]
    if len(exact):
        return float(min(exact))
    for xa, xb, ya, yb in zip(x[:-1], x[1:], y[:-1], y[1:]):
        if min(ya, yb) < quality < max(ya, yb):
            return float(xa + (quality - ya) * (xb - xa) / (yb - ya))
    raise ValueError("No supported inverse segment")
