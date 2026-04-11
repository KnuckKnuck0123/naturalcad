# NaturalCAD Publish Checklist

## Goal

Get NaturalCAD into a state where Noah can:
- create a GitHub repo
- push the canonical repo
- create a Hugging Face Space
- point the Space at this code
- start sharing it with testers

## Before publishing

- [ ] root `app.py` exists for Hugging Face Space
- [ ] root `requirements.txt` exists
- [ ] root `README.md` describes the project clearly
- [ ] generated artifacts are not committed
- [ ] Space can run without requiring a backend
- [ ] example prompts are present
- [ ] lightweight run logging is enabled

## GitHub publish

1. Create a new GitHub repo, probably `naturalcad`
2. From the canonical repo root:
   ```bash
   git init
   git add .
   git commit -m "Initial NaturalCAD MVP"
   git branch -M main
   git remote add origin <github-url>
   git push -u origin main
   ```
3. Confirm the repo shows:
   - `app.py`
   - `requirements.txt`
   - root `README.md`

## Hugging Face Space publish

1. Create a new Gradio Space
2. Connect the GitHub repo or upload the repo contents
3. Let Hugging Face build from:
   - `app.py`
   - `requirements.txt`
4. Test the example prompts first
5. Share the Space URL with friends

## If Hugging Face Space has dependency/runtime trouble

Do not panic.
Keep the same repo and UI path, then:
- leave HF as the frontend if possible
- offload execution to a container or VM
- plug backend execution in later

## First tester instructions

Ask testers to report:
- what prompt they tried
- what they expected
- what looked wrong
- whether the result was useful anyway
- any crashes or strange behavior
