# Put the MarginGraph demo online for free (Hugging Face Spaces)

Time: about 10 minutes. Cost: free (CPU basic: 2 vCPU, 16 GB RAM).
Nothing needs to be installed on your laptop for Option A.

## 1. Get the files

Download this branch as a ZIP and unzip it:
https://github.com/Sanskar1724/MarginGraph/archive/refs/heads/claude/project-thread-r1a0d1.zip
(after the PR is merged, use the ZIP of the branch it was merged into).

You only need the `space/` folder:

```
space/
  app.py              the Gradio app
  core.py             model + optimizer (numpy/pandas only)
  requirements.txt
  README.md           Space settings (the block between the --- lines)
  artifacts/          ease.npz (7 MB), catalog.csv, meta.json
```

## 2. Create the Space

1. Go to https://huggingface.co/join and make a free account (confirm the email).
2. Open https://huggingface.co/new-space
3. Fill in:
   * **Space name:** `margingraph`
   * **License:** MIT
   * **Select the Space SDK:** Gradio, template **Blank**
   * **Space hardware:** CPU basic · 2 vCPU · 16 GB · FREE
   * **Visibility:** Public (so stores can open it without logging in)
4. Click **Create Space**.

## 3A. Upload in the browser (easiest)

1. On the new Space page click the **Files** tab.
2. Click **+ Contribute** (top right of the file list), then **Upload files**.
3. Open your unzipped `space/` folder and drag **everything inside it**
   (`app.py`, `core.py`, `requirements.txt`, `README.md` and the whole `artifacts` folder)
   into the upload box. Say yes to replacing `README.md`.
4. Check that the list shows `artifacts/ease.npz`, `artifacts/catalog.csv`, `artifacts/meta.json`
   (with the folder name in front). If the folder was flattened, delete those three files
   and upload them again with the commit path set to `artifacts/`.
5. Commit message: `MarginGraph demo`. Click **Commit changes to main**.

## 3B. Or push with git (if you prefer the terminal)

1. Create a token: https://huggingface.co/settings/tokens, **Create new token**, type **Write**. Copy it.
2. Run:

```bash
git lfs install
git clone https://huggingface.co/spaces/<your-username>/margingraph hf-space
cp -r MarginGraph/space/* hf-space/
cd hf-space
git lfs track "*.npz"
git add .gitattributes .
git commit -m "MarginGraph demo"
git push            # username = your HF username, password = the token
```

Hugging Face refuses binary files that are not in LFS, which is why `*.npz` is tracked.

## 4. Wait for the build

Open the **App** tab. It shows *Building* for 2 to 4 minutes, then *Running*.
If it shows *Runtime error*, open **Logs** (top right) and send the last 20 lines.

## 5. Check it works

1. **Demo store:** a basket is pre-filled and two cards appear. Click **🎲 Real basket** a few times.
   Move the *Margin floor* slider to 0.40: items under 40% margin disappear from the MarginGraph card.
2. **Your store:** click **Products template** and **Orders template** to download sample CSVs,
   upload them back, click **Load my store**, pick 2 products, click **Recommend**.
3. **Backtest:** shows the measured numbers.

Your public link is `https://huggingface.co/spaces/<your-username>/margingraph`.
Replace `YOUR-HF-USERNAME` in `app.py` (How it works tab) with your username so the API snippet is right.

## Good to know

* Free Spaces sleep after 48 hours without visitors; the first visit after that takes about a minute to wake up.
* Uploaded store files live only in the visitor's session memory and are not saved.
* Run it on your own laptop instead: `pip install -r space/requirements.txt` then `python space/app.py`
  and open http://127.0.0.1:7860 (uses about 250 to 350 MB of RAM, fine on 8 GB).
* Rebuild the artifacts after changing the model: `python space/build_artifacts.py --xlsx online_retail_II.xlsx`
  (needs the full repo installed, about 20 seconds plus 2 minutes to read the xlsx).
