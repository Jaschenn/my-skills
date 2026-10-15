# my-skills

Agent skills (Claude Code / Claude.ai), one directory per skill.

| Skill | What it does |
|---|---|
| [`storytelling-viz`](storytelling-viz/SKILL.md) | Production- and publication-grade static charts with plotnine (zh / en): data-driven chart functions, business-reporting charts (KPI cards, target pace, driver trees), slide / doc / journal specs, SVG / PDF / PNG export and automatic layout QA. |

## storytelling-viz: checks before releasing

Requires [uv](https://docs.astral.sh/uv/). Run from any scratch directory (output goes to `./out/`):

```sh
uv run storytelling-viz/references/tests/edge_cases.py      # must print 76/76 as expected
uv run storytelling-viz/references/gallery.py               # every chart function, zh slide + en journal
uv run storytelling-viz/references/business_gallery.py      # business charts, zh slide + en doc
```

See [`storytelling-viz/CHANGELOG.md`](storytelling-viz/CHANGELOG.md) for versions.

## License

MIT, see [LICENSE](LICENSE). `storytelling-viz/references/swd_practices.md` paraphrases case studies from storytellingwithdata.com, with attribution (Knaflic, Cole).
