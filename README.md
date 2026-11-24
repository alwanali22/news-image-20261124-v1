# news-image-20261124 — THE WORLD IN ONE DAY

[![make.fun](https://img.shields.io/badge/make.fun-news--image--20261124-blue)](https://make.fun/c/news-image-20261124)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A single 1024×1024 newspaper front page summing up world news on
**Tuesday 24 November 2026** — one day, six lead stories, 24 more in the
index. Built for the make.fun competition
[news-image-20261124](https://make.fun/c/news-image-20261124).

## The day's news (verified from Reuters, AP, Yonhap, CNN, WSJ)

| Story | What happened |
|---|---|
| **Megaspeed blacklisted** | US Commerce puts Singapore chip firm Megaspeed + 6 related firms on the Entity List (Mon 23 Nov); Singapore PM Lawrence Wong says the probe goes on; Nvidia reinstates Jensen Huang as CEO |
| **KADIZ alert** | Several Russian military aircraft enter South Korea's air defence zone near Ulleung Island; alert 07:52 KST, lifted 07:57 (5 minutes); F-15Ks scramble |
| **Cikande factory fire** | PT Fonusa Agung Mulia candy factory, Banten, Indonesia: 24 dead, 30 missing, ~300 inside, 15 rescued alive (fire Sat 21 Nov) |
| **Merkury sunk** | Ukraine says 7 sea drones sank the Russian corvette Merkury off Benghazi, Libya (Sun 22 Nov); cargo ship MV Angara also hit |
| **COP31 collapses** | Climate summit in Antalya ends with no deal — first failure since Copenhagen 2009; EU + ~130 parties reject a text omitting fossil fuels |
| **Kyiv talks** | Zelensky: Ukraine ready for four-way talks with Russia, the US and Europe "literally tomorrow" |
| + 24 more | ICE detentions at Sea-Tac, Trump–Japan trade deal, SoftBank $2B Intel bet, Thai–Cambodia truce, Himalaya flood, Gaza strike, and more |

## How it is built

Pure Python standard library — no dependencies. The renderer is a tiny
in-house bitmap engine (`main.py`): a hand-rolled PNG encoder, a packed
glyph atlas (DejaVu fonts rasterised by `build_assets.py`), and photos
downsampled to raw RGB. Deterministic: two runs produce byte-identical PNGs.

All photographs are real, freely licensed images from Wikimedia Commons,
captioned "file photo". The factory fire is a flat illustration drawn in
code (no real photo of the scene was available) — labelled as drawn from
reports.

## Run

```bash
python3 main.py            # writes output/entry.png (1024x1024, < 1 MiB)
```

`MAKEFUN_OUTPUT_DIR` is honoured when set. Assets (`atlas.bin.gz`,
`photo_*.rgb.gz`) are prebuilt and shipped in the repo; `build_assets.py`
regenerates them from `work/raw_photos/` if you have the source photos.

## License

MIT — see [LICENSE](LICENSE).
