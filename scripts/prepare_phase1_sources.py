"""Select eight noncommercial CC BY-NC-SA MedleyDB recordings from MUSDB18-HQ.
No ODAQ inputs. Fetch ZIP ranges only; never silently download the full archive.
"""
import argparse, csv, hashlib, io, json, struct, time, urllib.request, zipfile
from pathlib import Path
import numpy as np
import soundfile as sf
from deepmushra_data.audioio import write_wav

RECORD = "https://zenodo.org/api/records/3338373"
EXPECTED_SIZE = 22656664047
EXPECTED_MD5 = "md5:12d4f2ecd55245a4688754dd76363103"
TRACKLIST_SHA256 = "5e0a9252774412be23971ebfb7d384c0b2f29842eed2fa16aab69cf825b332b1"
TRACKLIST = "https://raw.githubusercontent.com/sigsep/website/master/content/datasets/assets/tracklist.csv"
SELECTION = [
 ("Aimee Norwich - Child", "other", "tonal_instrument_stem"),
 ("Alexander Ross - Goodbye Bolero", "other", "tonal_instrument_stem"),
 ("Auctioneer - Our Future Faces", "drums", "percussion_stem"),
 ("Celestial Shore - Die For Us", "drums", "percussion_stem"),
 ("Clara Berry And Wooldog - Air Traffic", "vocals", "vocal_stem"),
 ("Creepoid - OldTree", "vocals", "vocal_stem"),
 ("Helado Negro - Mitad Del Mundo", "mixture", "mixture"),
 ("Steven Clark - Bounty", "mixture", "mixture"),
]

def fetch(url, headers=None):
    for attempt in range(4):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=60)
        except Exception:
            if attempt == 3: raise
            time.sleep(1 + attempt)

class RangeReader(io.RawIOBase):
    def __init__(self, url, size, base=0, length=None, shared=None):
        self.url, self.base, self.length = url, base, size if length is None else length
        self.pos = 0
        self.shared = shared if shared is not None else {"bytes": 0, "requests": 0, "cache": {}}
    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos
    def seek(self, offset, whence=0):
        position = offset if whence == 0 else self.pos + offset if whence == 1 else self.length + offset
        if position < 0: raise ValueError("Negative seek")
        self.pos = position
        return position
    def read(self, n=-1):
        n = min(self.length-self.pos, n if n >= 0 else self.length-self.pos)
        if n <= 0: return b""
        if n > 64*1024*1024: raise ValueError("Refusing unbounded range read")
        absolute = self.base + self.pos
        block = absolute // 65536 * 65536
        # Small header reads share a block; large audio reads request exactly the excerpt.
        low = block if n < 32768 else absolute
        high = min(self.base+self.length-1, block+65535) if n < 32768 else absolute+n-1
        key = (low, high)
        cache = self.shared["cache"]
        if key not in cache:
            with fetch(self.url, {"Range": f"bytes={low}-{high}"}) as response:
                if response.status != 206: raise RuntimeError("Server ignored bounded Range; aborting")
                if not response.headers.get("Content-Range", "").startswith(f"bytes {low}-{high}/"):
                    raise RuntimeError("Unexpected Content-Range")
                data = response.read(high-low+2)
                if len(data) != high-low+1: raise RuntimeError("Incomplete range")
            self.shared["requests"] += 1; self.shared["bytes"] += len(data)
            if len(cache) > 128: cache.clear()
            cache[key] = data
        data = cache[key][absolute-low:absolute-low+n]
        self.pos += len(data)
        return data
    def readinto(self, buffer):
        data = self.read(len(buffer)); buffer[:len(data)] = data; return len(data)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--output", default="data/phase1_sources")
    args=ap.parse_args(); root=Path(args.output).resolve(); root.mkdir(parents=True,exist_ok=True)
    if (root/"sources.jsonl").exists(): raise ValueError("Existing sources; refusing overwrite")
    record=json.load(fetch(RECORD)); (root/"musdb_record.json").write_text(json.dumps(record,indent=2))
    csv_text=fetch(TRACKLIST).read().decode(); (root/"musdb_tracklist.csv").write_text(csv_text)
    if hashlib.sha256(csv_text.encode()).hexdigest() != TRACKLIST_SHA256:
        raise RuntimeError("Tracklist changed; review attribution and repin before acquisition")
    license_url="https://sigsep.github.io/datasets/musdb.html"
    (root/"musdb_license.html").write_bytes(fetch(license_url).read())
    (root/"medleydb_license.html").write_bytes(fetch("https://medleydb.weebly.com/downloads.html").read())
    table={r["Track Name"]:r for r in csv.DictReader(io.StringIO(csv_text))}
    item=next(f for f in record["files"] if f["key"]=="musdb18hq.zip")
    if item["size"] != EXPECTED_SIZE or item["checksum"] != EXPECTED_MD5:
        raise RuntimeError("Archive metadata changed; review and repin")
    reader=RangeReader(item["links"]["self"],item["size"])
    archive=zipfile.ZipFile(reader)
    members=archive.infolist()
    (root/"archive_inventory.json").write_text(json.dumps([{"name":i.filename,"size":i.file_size,"compression":i.compress_type} for i in members],indent=2))
    rows=[]; receipts=[]
    for index,(track,stem,category) in enumerate(SELECTION):
        attribution=table[track]
        assert attribution["Source"]=="MedleyDB" and attribution["License"]=="CC BY-NC-SA"
        matches=[i for i in members if i.filename.endswith(f"/{track}/{stem}.wav")]
        if len(matches)!=1: raise RuntimeError((track,[i.filename for i in matches]))
        member=matches[0]
        if member.compress_type!=zipfile.ZIP_STORED:
            cache = root/"upstream_stems"; cache.mkdir(exist_ok=True)
            cached = cache/f"{index+1:02d}_{stem}.wav"
            if not cached.exists():
                temporary = cached.with_suffix(".partial")
                with archive.open(member) as source, temporary.open("wb") as target:
                    while block := source.read(8*1024*1024): target.write(block)
                temporary.rename(cached)  # ZipExtFile verifies CRC at EOF.
            import zlib
            crc=0
            with cached.open("rb") as check:
                while block := check.read(8*1024*1024): crc=zlib.crc32(block,crc)
            if crc != member.CRC: raise RuntimeError("Cached member CRC mismatch")
        else:
            cached = None
        reader.seek(member.header_offset); header=reader.read(30)
        if header[:4]!=b"PK\x03\x04": raise RuntimeError("Invalid ZIP local header")
        name_len,extra_len=struct.unpack_from("<HH",header,26)
        base=member.header_offset+30+name_len+extra_len
        audio_reader=RangeReader(reader.url,item["size"],base,member.file_size,reader.shared)
        with sf.SoundFile(cached if cached else audio_reader) as wav:
            assert wav.samplerate==44100 and wav.channels==2
            sr=wav.samplerate; count=8*sr
            candidates=[]
            for start_s in (20,40,60):
                if (start_s+8)*sr <= len(wav):
                    wav.seek(start_s*sr); audio=wav.read(count,dtype="float64",always_2d=True)
                    candidates.append((float(np.mean(audio**2)),start_s,audio))
            if not candidates: raise RuntimeError(f"No eight-second candidate in {track}")
            energy,start,audio=max(candidates,key=lambda x:x[0])
            if energy<=1e-8: raise RuntimeError(f"Selected inactive source {track}")
            info={"sample_rate":sr,"channels":wav.channels,"sample_count":len(wav),"subtype":wav.subtype}
        source_id="musdb18hq:"+track
        name=f"reference_{index+1:02d}.wav"; write_wav(root/name,audio,sr)
        provenance={"dataset":"MUSDB18-HQ / MedleyDB", "record_url":"https://zenodo.org/records/3338373",
          "artist_and_track":track, "genre":attribution["Genre"], "stem":stem,
          "license":"CC BY-NC-SA 4.0", "license_url":"https://creativecommons.org/licenses/by-nc-sa/4.0/",
          "license_evidence":license_url,"archive_member":member.filename,
          "archive_member_crc32":f"{member.CRC:08x}","full_member_crc_verified":cached is not None,
          "integrity_note":"Selected compressed member fully read and CRC verified; whole-archive MD5 not verified" if cached else "Only selected PCM ranges read; whole-member CRC and whole-archive MD5 not verified",
          "original_header":info,"excerpt_start_s":start,"excerpt_duration_s":8,
          "selection_rule":"Highest mean-square energy of fixed 8-second windows starting at 20,40,60 s; ties prefer earlier",
          "category_basis":"MUSDB stem designation; other is a multi-instrument tonal-content proxy, not a verified solo instrument",
          "modifications":"Excerpting and lossless DOUBLE WAV conversion; generator records any subsequent shared gain",
          "perceptual_cleanliness":"unverified; uncompressed release, not a human-quality certification",
          "permitted_use":"Noncommercial research; retain attribution and share-alike obligations; no audio in Git"}
        rows.append({"source_id":source_id,"source_file":name,"content_category":category,"source_provenance":provenance})
        receipts.append({"source_id":source_id,"sha256":hashlib.sha256((root/name).read_bytes()).hexdigest(),**provenance})
        print(track,stem,start,energy,reader.shared["bytes"],flush=True)
    (root/"sources.jsonl").write_text("".join(json.dumps(r,sort_keys=True)+"\n" for r in rows))
    (root/"acquisition_receipt.json").write_text(json.dumps({"upstream_archive_bytes":item["size"],"range_bytes":reader.shared["bytes"],"range_requests":reader.shared["requests"],"sources":receipts},indent=2)+"\n")
    print("COMPLETE",root,reader.shared["bytes"],flush=True)
if __name__=="__main__": main()
