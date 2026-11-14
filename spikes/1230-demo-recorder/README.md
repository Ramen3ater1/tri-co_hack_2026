# Demo recorder: shot-list takes in a scripted browser

**Tests:** can the web-app shots of `demo/video-shot-list.md` be recorded by a script (Playwright + Chromium, fake cursor drawn on the page) instead of by hand, the same every take?

**Result: yes for shot 3** (Sat 13:12): a 26 s, 1920×1080 take of Ben seeing "2 notes near here", selecting the general-will sentence, typing his note and Ana's and Sam's notes appearing. Each take deletes Ben's own notes first, so it can be re-run. **Shots 4 and 5 too** (Sat 13:30): shot 4 (39 s) asks, opens the AI explanation and clicks the first source, saving the source page it opens as a second video; shot 5 labels itself 5A (context-only, dev) or 5B (refusal, Owen's laptop copy run with `GATE_CONTEXT_ONLY=0`) from what the copy answers. Both first put back Ben's shot-3 note, quoting the selection exactly so the cached answers replay. Shot 6 (Preview + hotkey) stays by hand.

```bash
cd spikes/1230-demo-recorder
uv run --no-project --with playwright==1.65.2 playwright install chromium   # once
uv run --no-project --with playwright==1.65.2 python record.py {shot3|shot4|shot5} [--base https://dialectic-dev.yaggy.dev] [--headed]
```

The cursor is drawn on the page: a macOS-style pointer that eases in and out along a slight curve, smoothed at full frame rate, with a ripple on each click (`--no-cursor` leaves it out). Every take also saves the cursor's path and clicks as `<video name>.cursor.json` (seconds from the start of the video, pixel x/y), for redrawing a cursor in an editor.

Videos go to `~/Transfer/` named by shot and copy ("shot 4 - Ben asks, classmates then sources then AI (dev) HHMM.mp4"), with the page-loading seconds cut. It prints when each beat happens, for laying the voiceover on. Pacing, viewport, note text and the target copy are constants at the top of `record.py`. Playwright records at 1× only (a 2× device scale just pads the frame), so the viewport is the video size.
