# DFW Pauper weekly event poster: setup guide

Every Monday morning this posts "Pauper in DFW this week" with a schedule graphic,
built from `data/events.json` (the same file the website uses).

**Safe by default:** the Monday run only sends a *preview* to a private mod channel in
your Discord. Nothing goes public until you press "Run workflow" with mode `publish`,
or later turn on auto-publish. Events marked `"sample": true` are never posted, and a
week with no real events posts nothing.

You can set up platforms one at a time. Any platform without its secrets is skipped.

## 1. Where it lives

The code is in `poster/` and the schedule is `.github/workflows/weekly-posts.yml`.
It reads `data/events.json`, `data/site.json` and `assets/logo.png` from the repo root.
This repo is served publicly by GitHub Pages, so **never put keys or passwords in any file.**

**Where secrets go:** repo Settings > Secrets and variables > Actions > New repository secret.
Never paste these into chat, email, or a file in the repo.

## 2. Discord (free, 2 minutes)

1. In your server, make a private channel like `#mod-preview` (only you two can see it).
2. Edit Channel > Integrations > Webhooks > New Webhook > Copy Webhook URL.
   Save it as secret `DISCORD_PREVIEW_WEBHOOK_URL`.
3. Do the same for your public announcements/events channel.
   Save it as secret `DISCORD_WEBHOOK_URL`.

## 3. Bluesky (free, 2 minutes)

1. Bluesky > Settings > Privacy and security > App passwords > Add App Password.
2. Secrets: `BLUESKY_HANDLE` (e.g. `dfwpauper.bsky.social`) and `BLUESKY_APP_PASSWORD`.

## 4. X (pay per use, about $1/month)

1. Sign in to https://console.x.com as the DFW Pauper account.
2. Create a Project and an App. In the app's *User authentication settings*, set
   permissions to **Read and write**.
3. Under Keys and tokens, generate the **API Key and Secret** and the
   **Access Token and Secret** (generate the access token *after* setting Read and write).
4. Add a small credit balance (a few dollars lasts months; posts with links cost
   much more, which is why the X post has no link).
5. Secrets: `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`.

## 5. Facebook Page and Instagram (free, about 20 minutes)

1. **Instagram:** in the Instagram app, Settings > Account type and tools > switch to a
   Professional account (Creator or Business). Then link it to your Facebook Page
   (Facebook Page settings > Linked accounts > Instagram).
2. **Meta developer app:** at https://developers.facebook.com, My Apps > Create App >
   use case "Manage everything on your Page" (Business type). You must be a Page admin.
   Add the Instagram product as well.
3. In **Graph API Explorer**, select your app, then "Get Page Access Token" with
   permissions `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`,
   `instagram_basic`, `instagram_content_publish`, `business_management`.
4. Convert it to a **long-lived** token (Access Token Debugger > Extend Access Token),
   then call `GET /me/accounts` with that user token. The Page's `access_token` in the
   result does not expire. Save it as `META_PAGE_TOKEN`, and the Page `id` as `META_PAGE_ID`.
5. Call `GET /{page-id}?fields=instagram_business_account` and save the returned id as
   `INSTAGRAM_USER_ID`.

Your app can stay in Development mode because only your own Page is posted to.
Claude can walk you through this step by step.

## 6. Test, then go live

1. GitHub > Actions > **Weekly event posts** > Run workflow > mode `preview`.
   Check the post and image in `#mod-preview`.
2. Run again with mode `publish` and platforms `discord,bluesky` to test the free ones.
3. Then add `x,facebook,instagram`.
4. Once you trust it, add repo variable `AUTO_PUBLISH` = `true` so Mondays publish
   on their own. Remove it any time to go back to preview-only.

## Running it on your own computer

```
pip install -r poster/requirements.txt && python -m playwright install chromium
python -m poster.main --include-samples      # preview with sample events, writes output/
```
