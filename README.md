# Crypto & xStock Screener — Automated (GitHub Actions)

Runs all 4 screeners every 8 hours (00:00, 08:00, 16:00 UTC = 8am, 4pm,
midnight Philippine time) and emails you the HTML reports automatically.

## One-time setup (do this once)

### 1. Create a GitHub account (if you don't have one)
Go to github.com, sign up — free.

### 2. Create a new repository
- Click "+" (top right) → "New repository"
- Name it anything (e.g. `my-screeners`)
- Set to **Public** (this gives unlimited free Action minutes — private
  repos only get 2,000 free minutes/month, and the xStock runs alone can
  eat into that fast on CoinGecko's free tier)
- Click "Create repository"

### 3. Upload these files
On the new repo's page, click "uploading an existing file" and drag in
all the files from this folder, **keeping the folder structure intact**:
```
your-repo/
├── crypto_bullish.py
├── crypto_reverse.py
├── xstock_bullish.py
├── xstock_reverse.py
├── send_email.py
├── requirements.txt
├── .gitignore
└── .github/
    └── workflows/
        └── screener.yml
```
GitHub's web uploader supports dragging whole folders, so this should
carry the `.github/workflows/` structure over correctly. If it doesn't,
you may need to create the `.github/workflows/screener.yml` path
manually via "Add file → Create new file" and paste the content in.

### 4. Set up a Gmail App Password
This lets the script send email through your Gmail without using your
real password.
1. Go to myaccount.google.com/security
2. Turn on **2-Step Verification** if it isn't already on (required)
3. Go to myaccount.google.com/apppasswords
4. Create a new app password (name it e.g. "screener")
5. Copy the 16-character password shown — you won't see it again

### 5. Add your credentials as GitHub Secrets
In your repo: **Settings → Secrets and variables → Actions → New
repository secret**. Add these three, one at a time:

| Secret name | Value |
|---|---|
| `GMAIL_USER` | your full Gmail address |
| `GMAIL_APP_PASSWORD` | the 16-character app password from step 4 |
| `RECIPIENT_EMAIL` | where you want reports sent (can be the same Gmail) |

### 6. Test it manually
Go to the **Actions** tab in your repo → click the workflow name on the
left → click **Run workflow** (dropdown button) → **Run workflow**
(green button). This triggers an immediate run without waiting for the
schedule, so you can confirm everything works.

Check your email in a few minutes (xStock runs can take a while on
CoinGecko's free tier — be patient on the first run).

## After setup

You don't need to do anything else — it runs automatically every 8
hours from here on. You'll just get an email with 4 HTML attachments
each time.

## If something breaks

- Go to the **Actions** tab → click the failed run (marked with a red X)
  → click into each step to see the error log
- Common issues: a ticker got delisted (CoinGecko ID changed), Gmail
  blocked the login (re-check the App Password), or CoinGecko rate
  limits caused a script to time out (the 120-minute ceiling should
  prevent this, but a single ticker failing mid-run won't stop the
  whole report - it'll just show "n/a" for that one)
