"""Checks for model behavior, participant grouping, and fit/evaluation separation."""
import csv
import json
from pathlib import Path
import numpy as np
import pytest

from deepmushra_calibration.models import fit_curve, interpolate, fit_models, predict, select_shrinkage
from deepmushra_calibration.data import load_ratings, FILES
from deepmushra_calibration.experiment import coupled_weights


def fixture_rows():
    rows=[]
    for uid,cohort,bias in [("a","A",0),("b","B",0),("c","B",0),("d","B",0)]:
        for source,offset in [("bright",10),("dark",-10)]:
            for x,y in [(0,10),(1,50),(2,90)]:
                rows.append({"listener_id":uid,"stratum":cohort,"role":"calibration",
                             "source":source,"parameter":x,"score":y+offset+bias})
    return rows


def test_monotonic_regression_pools_violations():
    curve=fit_curve([0,1,2],[80,20,60],increasing=True,monotonic=True)
    np.testing.assert_allclose(curve["quality"],[50,50,60])
    reverse=fit_curve([0,1,2],[70,90,10],increasing=False,monotonic=True)
    np.testing.assert_allclose(reverse["quality"],[80,80,10])
    assert interpolate(curve,.5)==pytest.approx(50)


@pytest.mark.parametrize("value",[-1,3,float("nan")])
def test_out_of_domain_prediction_rejected(value):
    curve=fit_curve([0,1,2],[10,50,90],increasing=True,monotonic=False)
    with pytest.raises(ValueError):interpolate(curve,value)


def test_cohort_weights_and_source_fallback():
    rows=fixture_rows()
    for row in rows:
        if row["stratum"]=="B":row["score"]-=8
    fitted=fit_models(rows,{"A":3,"B":1},True,0)
    assert predict(fitted["lookup_linear"],1)==pytest.approx(48)
    assert predict(fitted["source_shrinkage"],1,"bright")==pytest.approx(58)
    assert predict(fitted["source_shrinkage"],1,"unseen")==pytest.approx(48)
    shrunk=fit_models(rows,{"A":3,"B":1},True,None)
    assert predict(shrunk["source_shrinkage"],1,"bright")==pytest.approx(48)


def test_fitting_rejects_evaluation_scores():
    rows=fixture_rows()
    rows[0]["role"]="evaluation"
    with pytest.raises(ValueError):fit_models(rows,{"A":1,"B":1},True,3)
    with pytest.raises(ValueError):select_shrinkage(rows,{"A":1,"B":1},True)


def test_penalty_selection_is_repeatable_and_uses_whole_listeners():
    rows=fixture_rows()
    first=select_shrinkage(rows,{"A":1,"B":3},True)
    second=select_shrinkage(rows,{"A":1,"B":3},True)
    assert first==second
    assert first[0]==0
    assert all({f["listener_id"] for f in candidate["folds"]}=={"a","b","c","d"} for candidate in first[1])


def test_bayesian_weights_keep_candidate_aliases_coupled():
    people=[{"listener_id":uid,"study":"test","proposed_role":"calibration"} for uid in ("old","new","other")]
    aliases=[{"earlier_listener_id":"old","later_listener_id":"new"}]
    draws,blocks=coupled_weights(people,aliases,"calibration",100,19)
    assert len(blocks)==2
    assert all(draw["old"]==draw["new"] for draw in draws)
    assert draws==coupled_weights(people,aliases,"calibration",100,19)[0]


def test_role_filter_does_not_parse_heldout_or_excluded_artifact_scores(tmp_path):
    root=tmp_path/"release"
    columns=["score","method","condition","process","item","subject"]
    for _,_,relative in FILES:
        path=root/relative
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open("w",newline="") as stream:
            writer=csv.DictWriter(stream,fieldnames=columns)
            writer.writeheader()
            if relative==FILES[0][2]:
                writer.writerows([
                    {"score":"50","method":"LP","condition":"Q1","process":"LP50","item":"LP_clip","subject":"Subject 1: DEID1"},
                    {"score":"DO_NOT_READ","method":"LP","condition":"Q1","process":"LP50","item":"LP_clip","subject":"Subject 2: DEID2"},
                    {"score":"DO_NOT_READ","method":"PE","condition":"Q1","process":"PE_foo","item":"PE_clip","subject":"Subject 1: DEID1"},
                    {"score":"DO_NOT_READ","method":"TM","condition":"Q1","process":"TM3k","item":"TM_clip","subject":"Subject 1: DEID1"},
                ])
    split=tmp_path/"split.csv"
    with split.open("w",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=["listener_id","proposed_role","stratum"])
        writer.writeheader()
        writer.writerows([
            {"listener_id":"2024-icassp::DEID1","proposed_role":"calibration","stratum":"A_DE"},
            {"listener_id":"2024-icassp::DEID2","proposed_role":"evaluation","stratum":"A_DE"},
        ])
    first=load_ratings(root,split,"calibration")
    assert len(first)==1 and first[0]["score"]==50
    target=root/FILES[0][2]
    target.write_text(target.read_text().replace("DO_NOT_READ","DIFFERENT_HELDOUT_SENTINEL"))
    assert load_ratings(root,split,"calibration")==first
