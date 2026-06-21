import { NextRequest, NextResponse } from "next/server";

const sessionCookie = "naturalcad_session";

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const backendUrl = process.env.NATURALCAD_BACKEND_URL || "http://127.0.0.1:8010";
  const gatewayKey = process.env.NATURALCAD_API_KEY || "";
  const origin = request.headers.get("origin");
  if (origin && origin !== request.nextUrl.origin && request.method !== "GET") {
    return NextResponse.json({ error: "Untrusted origin" }, { status: 403 });
  }

  const { path } = await context.params;
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  if (gatewayKey) headers.set("x-api-key", gatewayKey);
  const sessionId = request.cookies.get(sessionCookie)?.value;
  if (sessionId) headers.set("x-session-id", sessionId);
  const forwardedFor = request.headers.get("x-forwarded-for");
  if (forwardedFor) headers.set("x-forwarded-for", forwardedFor.split(",")[0].trim());

  const upstream = await fetch(`${backendUrl.replace(/\/$/, "")}/v1/${path.join("/")}`, {
    method: request.method,
    headers,
    body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer(),
    cache: "no-store",
  });
  const body = await upstream.arrayBuffer();
  let response = new NextResponse(body, {
    status: upstream.status,
    headers: { "content-type": upstream.headers.get("content-type") || "application/json" },
  });

  if (path.join("/") === "auth/guest" && upstream.ok) {
    const session = JSON.parse(new TextDecoder().decode(body)) as { session_id: string; actor_type: string; quotas: Record<string, number> };
    response = NextResponse.json({ actor_type: session.actor_type, quotas: session.quotas }, { status: upstream.status });
    response.cookies.set(sessionCookie, session.session_id, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 24 * 7,
    });
  }
  return response;
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
