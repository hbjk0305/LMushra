"""Do DAC / EnCodec keep high frequencies when RVQ is bypassed?

Two tests on the ODAQ reference clips, for the same codec checkpoints LMushra uses
(DAC 44kHz/8kbps, EnCodec 24kHz):

1. Reconstruction: x -> encoder -> decoder, with the continuous latent ("noRVQ")
   and with full RVQ ("RVQ"). Report per-band energy ratio (recon/orig, dB) and
   per-band SNR (orig / error, dB).
2. Latent sensitivity (what the LLM actually sees): relative change of the
   pooled pre-quantization latent when the clip is low-passed at fc, next to the
   energy removed by that low-pass.

Usage: $SWIFT_PYTHON eval/codec_hf/codec_hf.py [--out eval/codec_hf]
"""

import argparse
import glob
import json
import os

import numpy as np
import soundfile as sf
import torch
import torch.nn.functional as F
from scipy import signal

ODAQ = '/data/aisaro2/ODAQ/ODAQ_listening_test'
BANDS = [(0, 2e3), (2e3, 4e3), (4e3, 8e3), (8e3, 12e3), (12e3, 16e3), (16e3, 18e3), (18e3, 20e3), (20e3, 22.05e3)]
CUTOFFS = [4e3, 8e3, 11e3, 14e3, 16e3, 18e3, 20e3]
POOL = 4


def load_mono(path, sr):
    x, fs = sf.read(path, dtype='float32', always_2d=True)
    x = x.mean(1)
    g = np.gcd(int(fs), int(sr))
    return signal.resample_poly(x, sr // g, fs // g).astype(np.float32)


def lowpass(x, fc, sr):
    sos = signal.butter(16, fc, btype='low', fs=sr, output='sos')
    return signal.sosfiltfilt(sos, x).astype(np.float32)


def stft_mag(x, sr):
    f, _, Z = signal.stft(x, fs=sr, nperseg=2048, noverlap=1536)
    return f, np.abs(Z)


def band_mag_snr(x, y, sr):
    """Phase-insensitive per-band SNR: sum|X|^2 / sum(|X|-|Y|)^2 over STFT bins."""
    f, X = stft_mag(x, sr)
    _, Y = stft_mag(y, sr)
    out = []
    for lo, hi in BANDS:
        m = (f >= lo) & (f < hi)
        if lo >= sr / 2 or (X[m] ** 2).sum() < 1e-12:
            out.append(np.nan)
        else:
            out.append(10 * np.log10((X[m] ** 2).sum() / (((X[m] - Y[m]) ** 2).sum() + 1e-20)))
    return np.array(out)


def band_energy(x, sr):
    f, p = signal.welch(x, fs=sr, nperseg=4096)
    return np.array([p[(f >= lo) & (f < hi)].sum() if lo < sr / 2 else np.nan for lo, hi in BANDS])


class Dac:
    name, sr = 'DAC', 44100

    def __init__(self, dev):
        import dac
        self.m = dac.DAC.load(dac.utils.download(model_type='44khz', model_bitrate='8kbps', tag='0.0.1')).to(dev).eval()
        self.dev = dev

    def _pad(self, x):
        return F.pad(x, (0, (-x.shape[-1]) % self.m.hop_length))

    def encode(self, x):
        return self.m.encoder(self._pad(x))

    def decode(self, z, rvq):
        if rvq:
            z = self.m.quantizer(z, None)[0]  # all 9 codebooks
        return self.m.decoder(z)


class Encodec:
    name, sr = 'EnCodec', 24000

    def __init__(self, dev):
        from encodec import EncodecModel
        self.m = EncodecModel.encodec_model_24khz().to(dev).eval()
        self.m.set_target_bandwidth(24.0)  # max bandwidth = 32 codebooks

    def encode(self, x):
        return self.m.encoder(x)

    def decode(self, z, rvq):
        if rvq:
            codes = self.m.quantizer.encode(z, self.m.frame_rate, 24.0)
            z = self.m.quantizer.decode(codes)
        return self.m.decoder(z)


def lin_probe(items, folds=5):
    """Frame-level logistic probe, original vs low-passed, grouped by clip (held-out clips)."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    X = np.concatenate([np.concatenate([a, b]) for _, a, b in items])
    y = np.concatenate([np.r_[np.zeros(len(a)), np.ones(len(b))] for _, a, b in items])
    g = np.concatenate([np.full(len(a) + len(b), ci) for ci, a, b in items])
    accs = []
    for tr, te in GroupKFold(folds).split(X, y, g):
        clf = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000))
        clf.fit(X[tr], y[tr])
        accs.append(clf.score(X[te], y[te]))
    return float(np.mean(accs))


@torch.no_grad()
def run(codec, refs, dev):
    rec = {k: [] for k in ('orig', 'noRVQ', 'RVQ', 'err_noRVQ', 'err_RVQ')}
    msnr = {'noRVQ': [], 'RVQ': []}
    probe = {}  # fc -> list of (clip_idx, ref_frames, lp_frames)
    sens = []
    for ci, path in enumerate(refs):
        x = load_mono(path, codec.sr)
        xt = torch.from_numpy(x)[None, None].to(dev)
        z = codec.encode(xt)
        rec['orig'].append(band_energy(x, codec.sr))
        for mode, rvq in (('noRVQ', False), ('RVQ', True)):
            y = codec.decode(z, rvq)[0, 0, :len(x)].cpu().numpy()
            rec[mode].append(band_energy(y, codec.sr))
            rec['err_' + mode].append(band_energy(y - x, codec.sr))
            msnr[mode].append(band_mag_snr(x, y, codec.sr))
        zp = F.avg_pool1d(z, POOL, POOL, ceil_mode=True)
        row = {'clip': path}
        e_tot = (x ** 2).sum()
        for fc in CUTOFFS:
            if fc >= codec.sr / 2:
                continue
            xl = lowpass(x, fc, codec.sr)
            zl = F.avg_pool1d(codec.encode(torch.from_numpy(xl)[None, None].to(dev)), POOL, POOL, ceil_mode=True)
            row[f'removed_dB@{fc/1e3:g}k'] = float(10 * np.log10(((x - xl) ** 2).sum() / e_tot + 1e-12))
            row[f'dz@{fc/1e3:g}k'] = float((zl - zp).norm() / zp.norm())
            probe.setdefault(fc, []).append((ci, zp[0].T.cpu().numpy(), zl[0].T.cpu().numpy()))
        # Scale reference: latent change from a 1-frame-equivalent time shift (natural variation)
        xs = np.roll(x, 64)
        zs = F.avg_pool1d(codec.encode(torch.from_numpy(xs)[None, None].to(dev)), POOL, POOL, ceil_mode=True)
        row['dz@shift64'] = float((zs - zp).norm() / zp.norm())
        sens.append(row)
    rec = {k: np.array(v) for k, v in rec.items()}
    db = lambda a: 10 * np.log10(np.nanmedian(a, 0) + 1e-20)
    # Median over clips of per-clip ratios (bands with no content are excluded)
    def ratio(num, den):
        r = 10 * np.log10((rec[num] + 1e-20) / (rec[den] + 1e-20))
        r[rec['orig'] < 1e-9 * rec['orig'].sum(1, keepdims=True)] = np.nan  # band essentially empty
        return np.nanmedian(r, 0)
    out = {
        'bands': [f'{lo/1e3:g}-{hi/1e3:g}k' for lo, hi in BANDS],
        'orig_level_dB': db(rec['orig']).tolist(),
        'gain_noRVQ_dB': ratio('noRVQ', 'orig').tolist(),
        'gain_RVQ_dB': ratio('RVQ', 'orig').tolist(),
        'snr_noRVQ_dB': (-ratio('err_noRVQ', 'orig')).tolist(),
        'snr_RVQ_dB': (-ratio('err_RVQ', 'orig')).tolist(),
        'magsnr_noRVQ_dB': np.nanmedian(np.array(msnr['noRVQ']), 0).tolist(),
        'magsnr_RVQ_dB': np.nanmedian(np.array(msnr['RVQ']), 0).tolist(),
        'probe_acc': {f'{fc/1e3:g}k': lin_probe(v) for fc, v in probe.items()},
        'sensitivity_median': {k: float(np.median([r[k] for r in sens])) for k in sens[0] if k != 'clip'},
    }
    return out, sens


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.dirname(os.path.abspath(__file__)))
    args = ap.parse_args()
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    refs = sorted(glob.glob(f'{ODAQ}/*/reference.wav'))
    print(f'{len(refs)} reference clips')
    results = {}
    for cls in (Dac, Encodec):
        codec = cls(dev)
        summary, per_clip = run(codec, refs, dev)
        results[codec.name] = summary
        with open(os.path.join(args.out, f'sensitivity_{codec.name}.json'), 'w') as f:
            json.dump(per_clip, f, indent=1)
        print(f'\n== {codec.name} ({codec.sr} Hz) ==')
        keys = ('orig_level_dB', 'gain_noRVQ_dB', 'gain_RVQ_dB', 'magsnr_noRVQ_dB', 'magsnr_RVQ_dB', 'snr_noRVQ_dB', 'snr_RVQ_dB')
        print(f"{'band':>10} " + ' '.join(f'{k.replace("_dB", ""):>14}' for k in keys))
        for i, b in enumerate(summary['bands']):
            print(f'{b:>10} ' + ' '.join(f'{summary[k][i]:>14.1f}' for k in keys))
        print('probe acc (held-out clips, chance .5):', summary['probe_acc'])
        print('latent sensitivity (median):', json.dumps(summary['sensitivity_median'], indent=1))
        del codec
        torch.cuda.empty_cache()
    with open(os.path.join(args.out, 'summary.json'), 'w') as f:
        json.dump(results, f, indent=1)


if __name__ == '__main__':
    main()
