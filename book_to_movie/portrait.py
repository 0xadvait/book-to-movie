"""An engraved portrait of a real person from a public-domain Wikimedia Commons file. Refuses the file unless Commons marks
it public domain, finds the face, crops head and shoulders and engraves it. Sources are logged to source/pd/SOURCES.txt."""
import json
import re
import urllib.parse
import urllib.request

import cv2

from .engrave import photo_engrave

USER_AGENT = "book-to-movie/0.1 (https://github.com/0xadvait/book-to-movie)"


def make_portrait(p, ch, slug, title, crop=None):
    api = ("https://commons.wikimedia.org/w/api.php?action=query&prop=imageinfo&iiprop=url|extmetadata|size&format=json&titles="
           + urllib.parse.quote(title))
    with urllib.request.urlopen(urllib.request.Request(api, headers={"User-Agent": USER_AGENT})) as r:
        info = json.load(r)
    page = next(iter(info["query"]["pages"].values()))
    if "imageinfo" not in page:
        raise SystemExit(f"Commons has no file called {title!r}")
    ii = page["imageinfo"][0]
    md = ii.get("extmetadata", {})
    lic = (md.get("LicenseShortName", {}).get("value", "") + " " + md.get("UsageTerms", {}).get("value", "")).lower()
    if not ("public domain" in lic or re.search(r"\bpd\b|pd-", lic)):
        raise SystemExit(f"refusing {title}: Commons licence is {lic!r}")

    src_dir = p.root / "source" / "pd"
    src_dir.mkdir(parents=True, exist_ok=True)
    ext = "." + ii["url"].split("?")[0].rsplit(".", 1)[-1].lower()
    path = src_dir / f"{slug}{ext}"
    if not path.exists():
        with urllib.request.urlopen(urllib.request.Request(ii["url"], headers={"User-Agent": USER_AGENT})) as r:
            path.write_bytes(r.read())
    artist = re.sub(r"<[^>]+>", "", md.get("Artist", {}).get("value", ""))[:120]
    date = re.sub(r"<[^>]+>", "", md.get("DateTimeOriginal", {}).get("value", ""))[:60]
    date = date.split("date QS")[0].strip()
    log, entry = src_dir / "SOURCES.txt", f"{slug}: {title} | {artist} | {date} | {lic.strip()} | {ii['url']}\n"
    if not log.exists() or entry not in log.read_text():
        with open(log, "a") as f:
            f.write(entry)

    img = cv2.imread(str(path))
    if img is None:
        raise SystemExit(f"could not read {path}: use a JPEG or PNG file from Commons")
    H, W = img.shape[:2]
    if crop:
        x0, y0, x1, y1 = crop
    else:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        faces = cascade.detectMultiScale(gray, 1.1, 6, minSize=(max(40, W // 12), max(40, W // 12)))
        if len(faces) == 0:
            raise SystemExit(f"no face found in {title}: pass --crop x0,y0,x1,y1 (the image is {W}x{H})")
        fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
        crop_w, crop_h, cx = fw * 2.5, fw * 2.5 * 1.25, fx + fw / 2
        x0, x1 = int(max(0, cx - crop_w / 2)), int(min(W, cx + crop_w / 2))
        y0 = int(max(0, fy - fh * 0.72))
        y1 = int(min(H, y0 + crop_h))
    out = p.art_assets(ch, "portraits") / f"{slug}.png"
    photo_engrave(path, out, (x0, y0, x1, y1), (640, 800), angle=6, pitch=3.2, warp=4.5, gamma=1.05, oval=0.9, frame=True,
                  paper=p.look["paper"], ink=p.look["ink"])
    print(f"portrait {slug}: crop {x0},{y0},{x1},{y1} of {W}x{H}; {lic.strip()}; {artist} {date} -> {out}")
    return out
