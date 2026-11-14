# Demo recorder: shot-list takes in a scripted browser

**Tests:** can the web-app shots of `demo/video-shot-list.md` be recorded by a script (Playwright + Chromium, fake cursor drawn on the page) instead of by hand, the same every take?

**Result: yes for shot 3** (Sat 13:12): a 26 s, 1920×1080 take of Ben seeing "2 notes near here", selecting the general-will sentence, typing his note and Ana's and Sam's notes appearing. Each take deletes Ben's own notes first, so it can be re-run. Shots 4/5 are the next to add; shot 6 (Preview + hotkey) stays by hand.

```bash
cd spikes/1230-demo-recorder
uv run --no-project --with playwright==1.65.2 playwright install chromium   # once
uv run --no-project --with playwright==1.65.2 python record.py shot3 [--base https://dialectic-dev.yaggy.dev] [--headed]
```

Videos go to `~/Transfer/` named by shot ("shot 3 - Ben unlocks the notes - HHMM.mp4"), with the page-loading seconds cut. It prints when each beat happens, for laying the voiceover on. Pacing, viewport, note text and the target copy are constants at the top of `record.py`. Playwright records at 1× only (a 2× device scale just pads the frame), so the viewport is the video size.
