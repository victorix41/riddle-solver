# RiddleSolver Frontend

A single static page (`index.html`, no build step, no framework) that calls
the RiddleSolver FastAPI backend. Deployable to Vercel as-is.

## Local preview

Just open `index.html` directly in your browser, or serve it locally:

```bash
python -m http.server 5500
```
then visit `http://localhost:5500`.

Make sure the FastAPI backend is running separately (see the backend's
README) at `http://localhost:8000` — that's the default value prefilled in
the "API host" field on the page.

## Deploying to Vercel

1. Push this folder to its own GitHub repo (or a subfolder of an existing
   one — Vercel lets you set a "Root Directory" if so).
2. Go to [vercel.com](https://vercel.com) → **Add New** → **Project**.
3. Import the GitHub repo.
4. Framework preset: choose **Other** (this is a plain static site, no
   build command needed). Leave Build/Output settings as default/empty.
5. Click **Deploy**. Vercel gives you a URL like
   `https://riddle-solver-frontend.vercel.app`.

## Using it

Open your Vercel URL. At the top of the page:
- **API host** — defaults to `http://localhost:8000`. Leave this as-is if
  you (the person viewing the page) are running the FastAPI backend locally
  on the same laptop. Change it only if you've tunneled your backend out
  (e.g. via ngrok) to a public URL.
- **Mode** — `answer_with_explanation` (default), `answer_only`, or
  `guided_hint`.

Type a riddle, press Enter or click **Solve Riddle**.

## Important limitation

This page calling `http://localhost:8000` only works for whoever is viewing
it *on the same machine that's running the FastAPI + Ollama backend*. If a
teammate, grader, or anyone else opens your Vercel link on their own
computer, the request will fail (their `localhost:8000` has nothing running).
This is expected — for a course project demo you're personally driving, it's
not a problem. If you need it to work for other people independently, you'd
need to expose your backend at a real public URL (tunnel or hosted server)
and update the "API host" field accordingly.
