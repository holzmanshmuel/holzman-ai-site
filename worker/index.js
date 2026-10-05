// holzman-ai-site Worker.
//
// The site is static: every request is answered by the assets in this repo, exactly
// as before. The one exception is POST /api/contact, the homepage contact form. It used
// to post straight to a third-party relay (formsubmit.co with a Gmail address in the
// URL), which is the pattern Google Safe Browsing reads as a phishing form on a new
// domain (HOLZMAN-214). The form now posts to this same origin, and the Worker hands
// the message to n8n, which emails it to shmuel@holzman.ai.
//
// CONTACT_WEBHOOK_URL is a Worker secret (wrangler secret put CONTACT_WEBHOOK_URL).
// It never appears in the page or in this public repo.

const LIMITS = { name: 200, email: 320, company: 200, referrer: 200, message: 5000 };
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/api/contact") return handleContact(request, env, url);
    return env.ASSETS.fetch(request);
  },
};

async function handleContact(request, env, url) {
  if (request.method !== "POST") {
    return json({ ok: false, error: "method_not_allowed" }, 405, { Allow: "POST" });
  }

  // Browsers always send Origin on a cross-site POST; only this site's own page may post.
  const origin = request.headers.get("Origin");
  if (!origin || hostOf(origin) !== url.host) {
    return json({ ok: false, error: "forbidden" }, 403);
  }

  let fields;
  try {
    const type = request.headers.get("Content-Type") || "";
    if (type.includes("application/json")) {
      fields = await request.json();
    } else {
      const form = await request.formData();
      fields = {};
      for (const [key, value] of form.entries()) {
        if (typeof value === "string") fields[key] = value;
      }
    }
  } catch {
    return json({ ok: false, error: "bad_request" }, 400);
  }
  if (!fields || typeof fields !== "object" || Array.isArray(fields)) {
    return json({ ok: false, error: "bad_request" }, 400);
  }

  // Only plain strings count; anything else (objects, numbers from crafted JSON) is empty.
  const text = (value) => (typeof value === "string" ? value : "");
  const field = (key) => text(fields[key]).trim().slice(0, LIMITS[key]);
  const inquiry = {
    name: field("name"),
    email: field("email"),
    company: field("company"),
    referrer: field("referrer"),
    message: field("message"),
  };

  // Honeypot: a hidden "website" field people never see. Bots that fill it get a quiet
  // success and nothing is forwarded.
  if (text(fields.website).trim()) return json({ ok: true });

  if (!inquiry.name || !EMAIL_RE.test(inquiry.email)) {
    return json({ ok: false, error: "invalid" }, 422);
  }

  if (!env.CONTACT_WEBHOOK_URL) {
    return json({ ok: false, error: "unavailable" }, 503);
  }

  try {
    const res = await fetch(env.CONTACT_WEBHOOK_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json", "User-Agent": "holzman-ai-site/contact" },
      body: JSON.stringify(inquiry),
    });
    if (!res.ok) return json({ ok: false, error: "upstream" }, 502);
  } catch {
    return json({ ok: false, error: "upstream" }, 502);
  }

  return json({ ok: true });
}

function hostOf(value) {
  try {
    return new URL(value).host;
  } catch {
    return "";
  }
}

function json(body, status = 200, headers = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store", ...headers },
  });
}
