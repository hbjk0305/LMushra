import argparse
import json
from pathlib import Path

from .experiment import fit, evaluate
from .figures import figures


def main():
    parser=argparse.ArgumentParser(description="ODAQ-informed, listener-held-out calibration POC")
    commands=parser.add_subparsers(dest="command",required=True)
    for command in ("fit","evaluate"):
        sub=commands.add_parser(command)
        sub.add_argument("--release",type=Path,required=True)
        sub.add_argument("--split",type=Path,required=True)
        sub.add_argument("--aliases",type=Path,required=True)
        sub.add_argument("--output",type=Path,required=True)
        sub.add_argument("--bootstrap-repetitions",type=int,default=2000)
    sub=commands.add_parser("figures")
    sub.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.command=="figures":
        result=figures(args.output)
    else:
        if args.bootstrap_repetitions<100:
            parser.error("Use at least 100 resampling repetitions")
        function=fit if args.command=="fit" else evaluate
        result=function(args.release,args.split,args.aliases,args.output,args.bootstrap_repetitions)
    print(json.dumps(result,indent=2,allow_nan=False))


if __name__=="__main__":
    main()
