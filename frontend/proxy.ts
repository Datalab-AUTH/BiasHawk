import { NextResponse, type NextRequest } from "next/server";

/**
 * A cheap gate: is there a session cookie at all?
 *
 * This is not the authorization check , the API enforces that on every request,
 * and every queryset is scoped to its owner. This only avoids rendering the
 * dashboard shell for someone who is obviously signed out.
 *
 * Named `proxy` rather than `middleware`: Next 16 deprecated that filename and
 * export in favour of this one.
 */
const PUBLIC_PATHS = ["/sign-in", "/sign-up"];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const hasSession =
    request.cookies.has("sessionid") || request.cookies.has("__Secure-sessionid");

  if (PUBLIC_PATHS.includes(pathname)) {
    if (hasSession) {
      return NextResponse.redirect(new URL("/dashboard/use-cases", request.url));
    }
    return NextResponse.next();
  }

  if (!hasSession) {
    const signIn = new URL("/sign-in", request.url);
    if (pathname !== "/") signIn.searchParams.set("next", pathname);
    return NextResponse.redirect(signIn);
  }

  return NextResponse.next();
}

export const config = {
  // Pages only. A file in /public is not a page to sign in to, and gating one
  // answers an image request with the sign-in HTML: the browser then reports a
  // broken image, and next/image reports "not a valid image". The list used to
  // hold `.svg` alone, which is why the logo loaded and nothing else did.
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|avif|ico|woff2?|ttf|otf|txt|xml)$).*)",
  ],
};
