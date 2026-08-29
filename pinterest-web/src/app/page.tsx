import Link from "next/link"

export default function LandingPage() {
  return (
    <div className="flex min-h-[calc(100dvh-72px)] flex-col">
      {/* Hero Section */}
      <section className="flex flex-1 flex-col items-center justify-center px-6 py-24 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-lg">
          <svg className="h-9 w-9" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 0C5.373 0 0 5.373 0 12c0 5.084 3.163 9.426 7.627 11.174-.105-.949-.2-2.405.042-3.441.218-.937 1.407-5.965 1.407-5.965s-.359-.719-.359-1.782c0-1.668.967-2.914 2.171-2.914 1.023 0 1.518.769 1.518 1.69 0 1.029-.655 2.568-.994 3.995-.283 1.194.599 2.169 1.777 2.169 2.133 0 3.772-2.249 3.772-5.495 0-2.873-2.064-4.882-5.012-4.882-3.414 0-5.418 2.561-5.418 5.207 0 1.031.397 2.138.893 2.738a.36.36 0 01.083.345l-.333 1.36c-.053.22-.174.267-.402.161-1.499-.698-2.436-2.889-2.436-4.649 0-3.785 2.75-7.262 7.929-7.262 4.163 0 7.398 2.967 7.398 6.931 0 4.136-2.607 7.464-6.227 7.464-1.216 0-2.359-.631-2.75-1.378l-.748 2.853c-.271 1.043-1.002 2.35-1.492 3.146C9.57 23.812 10.763 24 12 24c6.627 0 12-5.373 12-12S18.627 0 12 0z" />
          </svg>
        </div>

        <h1 className="mt-8 text-5xl font-bold tracking-tight sm:text-6xl">
          Your Pinterest, on autopilot
        </h1>
        <p className="mt-6 max-w-2xl text-lg text-muted-foreground">
          Upload images once. Get AI-written titles, descriptions, and keywords.
          We publish at the best times so you don&apos;t have to.
        </p>

        <div className="mt-10 flex gap-4">
          <Link
            href="/dashboard"
            className="inline-flex h-12 items-center rounded-lg bg-primary px-6 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
          >
            Open Dashboard
          </Link>
          <a
            href="https://wallpeps.com"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex h-12 items-center rounded-lg border border-border bg-background px-6 text-sm font-medium transition-colors hover:bg-muted"
          >
            Visit Wallpeps
          </a>
        </div>
      </section>

      {/* Features Section */}
      <section className="border-t bg-muted/30 px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <h2 className="text-center text-3xl font-bold tracking-tight">
            Three steps, done
          </h2>
          <div className="mt-12 grid gap-8 md:grid-cols-3">
            <div className="rounded-xl border bg-card p-6">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                </svg>
              </div>
              <h3 className="mt-4 text-lg font-semibold">Drop your images</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                Drag, drop, or paste. PNG, JPG, JPEG, WebP &mdash; we handle the rest.
              </p>
            </div>

            <div className="rounded-xl border bg-card p-6">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                </svg>
              </div>
              <h3 className="mt-4 text-lg font-semibold">AI writes the copy</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                Titles, descriptions, alt text, keywords &mdash; generated from what the image actually shows.
              </p>
            </div>

            <div className="rounded-xl border bg-card p-6">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
                </svg>
              </div>
              <h3 className="mt-4 text-lg font-semibold">Schedule and forget</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                Pick a time or let us choose. Pins go live when your audience is most active.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Social Proof - Real metrics instead of fake testimonials */}
      <section className="px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
            <div className="text-center">
              <p className="text-4xl font-bold tracking-tight">184</p>
              <p className="mt-1 text-sm text-muted-foreground">Pins processed</p>
            </div>
            <div className="text-center">
              <p className="text-4xl font-bold tracking-tight">31</p>
              <p className="mt-1 text-sm text-muted-foreground">Scheduled</p>
            </div>
            <div className="text-center">
              <p className="text-4xl font-bold tracking-tight">5</p>
              <p className="mt-1 text-sm text-muted-foreground">AI providers</p>
            </div>
            <div className="text-center">
              <p className="text-4xl font-bold tracking-tight">24/7</p>
              <p className="mt-1 text-sm text-muted-foreground">Auto-publishing</p>
            </div>
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section className="border-t bg-muted/30 px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <h2 className="text-center text-3xl font-bold tracking-tight">
            Pricing
          </h2>
          <p className="mt-4 text-center text-muted-foreground">
            Start free, scale when ready
          </p>
          <div className="mt-12 grid gap-8 md:grid-cols-3">
            {/* Free Plan */}
            <div className="rounded-xl border bg-card p-8">
              <h3 className="text-lg font-semibold">Starter</h3>
              <div className="mt-4">
                <span className="text-4xl font-bold">$0</span>
                <span className="text-muted-foreground">/month</span>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">
                Try it out, no commitment
              </p>
              <ul className="mt-6 space-y-3 text-sm">
                <li className="flex items-center gap-2">
                  <svg className="h-4 w-4 text-primary" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                  50 pins per month
                </li>
                <li className="flex items-center gap-2">
                  <svg className="h-4 w-4 text-primary" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                  AI-generated descriptions
                </li>
                <li className="flex items-center gap-2">
                  <svg className="h-4 w-4 text-primary" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                  1 Pinterest account
                </li>
              </ul>
              <Link
                href="/dashboard"
                className="mt-8 block w-full rounded-lg border border-border bg-background py-3 text-center text-sm font-medium transition-colors hover:bg-muted"
              >
                Get started
              </Link>
            </div>

            {/* Pro Plan */}
            <div className="relative rounded-xl border-2 border-primary bg-card p-8 shadow-lg">
              <h3 className="text-lg font-semibold">Pro</h3>
              <div className="mt-4">
                <span className="text-4xl font-bold">$19</span>
                <span className="text-muted-foreground">/month</span>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">
                For regular pinners
              </p>
              <ul className="mt-6 space-y-3 text-sm">
                <li className="flex items-center gap-2">
                  <svg className="h-4 w-4 text-primary" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                  500 pins per month
                </li>
                <li className="flex items-center gap-2">
                  <svg className="h-4 w-4 text-primary" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                  SEO-optimized keywords
                </li>
                <li className="flex items-center gap-2">
                  <svg className="h-4 w-4 text-primary" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                  5 Pinterest accounts
                </li>
                <li className="flex items-center gap-2">
                  <svg className="h-4 w-4 text-primary" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                  Analytics dashboard
                </li>
              </ul>
              <Link
                href="/dashboard"
                className="mt-8 block w-full rounded-lg bg-primary py-3 text-center text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
              >
                Start free trial
              </Link>
            </div>

            {/* Business Plan */}
            <div className="rounded-xl border bg-card p-8">
              <h3 className="text-lg font-semibold">Business</h3>
              <div className="mt-4">
                <span className="text-4xl font-bold">$49</span>
                <span className="text-muted-foreground">/month</span>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">
                Teams and agencies
              </p>
              <ul className="mt-6 space-y-3 text-sm">
                <li className="flex items-center gap-2">
                  <svg className="h-4 w-4 text-primary" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                  Unlimited pins
                </li>
                <li className="flex items-center gap-2">
                  <svg className="h-4 w-4 text-primary" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                  Team collaboration
                </li>
                <li className="flex items-center gap-2">
                  <svg className="h-4 w-4 text-primary" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                  Unlimited accounts
                </li>
                <li className="flex items-center gap-2">
                  <svg className="h-4 w-4 text-primary" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                  Priority support
                </li>
              </ul>
              <Link
                href="/dashboard"
                className="mt-8 block w-full rounded-lg border border-border bg-background py-3 text-center text-sm font-medium transition-colors hover:bg-muted"
              >
                Contact us
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* App Info Section - Required for Pinterest API */}
      <section className="px-6 py-20">
        <div className="mx-auto max-w-3xl">
          <h2 className="text-center text-3xl font-bold tracking-tight">
            About Wallpeps
          </h2>
          <div className="mt-8 space-y-6 text-center">
            <p className="text-lg text-muted-foreground">
              <strong>App Name:</strong> Wallpeps Staging App
            </p>
            <p className="text-lg text-muted-foreground">
              <strong>Company:</strong> Wallpeps
            </p>
            <p className="text-lg text-muted-foreground">
              <strong>Website:</strong>{" "}
              <a
                href="https://wallpeps.com"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary underline-offset-4 hover:underline"
              >
                wallpeps.com
              </a>
            </p>
            <p className="text-lg text-muted-foreground">
              <strong>Privacy Policy:</strong>{" "}
              <Link
                href="/privacy"
                className="text-primary underline-offset-4 hover:underline"
              >
                /privacy
              </Link>
            </p>
          </div>

          <div className="mt-12 rounded-xl border bg-muted/30 p-8">
            <h3 className="text-xl font-semibold">App Purpose</h3>
            <p className="mt-4 text-muted-foreground">
              Pinterest Automation Dashboard - This app automatically discovers, analyzes, schedules,
              and publishes visual content (pins) to Pinterest on behalf of the account owner.
              It provides AI-generated titles, descriptions, and alt text for each pin, manages boards,
              tracks performance analytics, and generates engagement reports. All content publishing
              is controlled by the account owner through a web dashboard.
            </p>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t px-6 py-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 sm:flex-row">
          <p className="text-sm text-muted-foreground">
            &copy; {new Date().getFullYear()} Wallpeps. All rights reserved.
          </p>
          <div className="flex gap-6">
            <a
              href="https://wallpeps.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              Website
            </a>
            <Link
              href="/privacy"
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              Privacy Policy
            </Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
