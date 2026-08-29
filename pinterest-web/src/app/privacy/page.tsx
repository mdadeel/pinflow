import Link from "next/link"

export default function PrivacyPolicyPage() {
  const sections = [
    { id: "overview", title: "1. Overview" },
    { id: "collection", title: "2. Information We Collect" },
    { id: "usage", title: "3. How We Use Your Information" },
    { id: "sharing", title: "4. Data Sharing and Disclosure" },
    { id: "pinterest", title: "5. Pinterest Data Usage" },
    { id: "security", title: "6. Data Security" },
    { id: "retention", title: "7. Data Retention" },
    { id: "rights", title: "8. Your Rights" },
    { id: "third-party", title: "9. Third-Party Links" },
    { id: "children", title: "10. Children's Privacy" },
    { id: "changes", title: "11. Changes to This Policy" },
    { id: "contact", title: "12. Contact Us" },
    { id: "compliance", title: "13. Pinterest Developer Compliance" },
  ]

  return (
    <div className="mx-auto max-w-6xl px-6 py-12 lg:py-20">
      {/* Back to Home Link */}
      <div className="mb-8">
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <svg
            className="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18"
            />
          </svg>
          Back to Home
        </Link>
      </div>

      <div className="grid gap-12 lg:grid-cols-[240px_1fr]">
        {/* Table of Contents - Desktop Sticky Sidebar */}
        <aside className="hidden lg:block">
          <div className="sticky top-24">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-4">
              On this page
            </h2>
            <nav className="flex flex-col gap-2">
              {sections.map((sec) => (
                <a
                  key={sec.id}
                  href={`#${sec.id}`}
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors py-1 hover:translate-x-1 duration-150 inline-block"
                >
                  {sec.title}
                </a>
              ))}
            </nav>
          </div>
        </aside>

        {/* Content Area */}
        <article className="prose dark:prose-invert max-w-none">
          <header className="mb-12 border-b pb-8">
            <h1 className="text-4xl font-extrabold tracking-tight lg:text-5xl bg-gradient-to-r from-primary to-purple-600 bg-clip-text text-transparent">
              Privacy Policy
            </h1>
            <p className="mt-4 text-sm text-muted-foreground">
              <strong>Effective Date:</strong> August 27, 2026
            </p>
          </header>

          <div className="space-y-12">
            {/* Section 1 */}
            <section id="overview" className="scroll-mt-24">
              <h2 className="text-2xl font-bold tracking-tight mb-4 text-foreground">
                1. Overview
              </h2>
              <p className="text-muted-foreground leading-relaxed">
                PinFlow (&ldquo;we&rdquo;, &ldquo;our&rdquo;, or &ldquo;us&rdquo;) is a Pinterest automation platform developed by WallPeps. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use our PinFlow platform.
              </p>
            </section>

            {/* Section 2 */}
            <section id="collection" className="scroll-mt-24 border-t pt-8">
              <h2 className="text-2xl font-bold tracking-tight mb-4 text-foreground">
                2. Information We Collect
              </h2>
              <p className="text-muted-foreground leading-relaxed mb-6">
                We collect information to provide, maintain, and improve our services, as well as to authenticate and execute requests on your behalf.
              </p>
              
              <div className="grid gap-6 md:grid-cols-3">
                <div className="rounded-xl border bg-card p-5 shadow-sm">
                  <h3 className="font-semibold text-foreground mb-2">2.1 You Provide</h3>
                  <ul className="text-sm text-muted-foreground space-y-2 list-disc pl-4">
                    <li>Pinterest account credentials (via secure OAuth tokens)</li>
                    <li>Board details (names, descriptions)</li>
                    <li>Pin content (images, titles, descriptions, keywords)</li>
                    <li>Scheduling preferences</li>
                  </ul>
                </div>
                
                <div className="rounded-xl border bg-card p-5 shadow-sm">
                  <h3 className="font-semibold text-foreground mb-2">2.2 Automatically</h3>
                  <ul className="text-sm text-muted-foreground space-y-2 list-disc pl-4">
                    <li>Platform usage statistics</li>
                    <li>API request logs (for debugging and optimization)</li>
                    <li>Error reports and performance metrics</li>
                  </ul>
                </div>
                
                <div className="rounded-xl border bg-card p-5 shadow-sm">
                  <h3 className="font-semibold text-foreground mb-2">2.3 From Pinterest</h3>
                  <ul className="text-sm text-muted-foreground space-y-2 list-disc pl-4">
                    <li>Public profile details</li>
                    <li>Pinterest Board information</li>
                    <li>Pin performance analytics (impressions, clicks, saves)</li>
                    <li>Account preferences</li>
                  </ul>
                </div>
              </div>
            </section>

            {/* Section 3 */}
            <section id="usage" className="scroll-mt-24 border-t pt-8">
              <h2 className="text-2xl font-bold tracking-tight mb-4 text-foreground">
                3. How We Use Your Information
              </h2>
              <p className="text-muted-foreground leading-relaxed mb-4">
                We use the collected information for various operational and improvement purposes:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>To provide, secure, and maintain PinFlow services.</li>
                <li>To schedule and automate Pinterest pin creation on your behalf.</li>
                <li>To retrieve and analyze Pinterest performance metrics.</li>
                <li>To improve platform features, AI vision generation, and user experience.</li>
                <li>To communicate service updates or alert you to issues.</li>
                <li>To comply with regulatory and legal obligations.</li>
              </ul>
            </section>

            {/* Section 4 */}
            <section id="sharing" className="scroll-mt-24 border-t pt-8">
              <h2 className="text-2xl font-bold tracking-tight mb-4 text-foreground">
                4. Data Sharing and Disclosure
              </h2>
              <p className="text-muted-foreground leading-relaxed">
                We do not sell, trade, or rent your personal information to third parties. We may disclose information under the following limited circumstances:
              </p>
              <ul className="list-disc pl-6 mt-4 space-y-2 text-muted-foreground">
                <li>With service providers who assist us in operating our platform (e.g. database hosting).</li>
                <li>To comply with legal requirements, government requests, or to protect rights and safety.</li>
                <li>During business transitions (mergers, acquisitions, asset transfers).</li>
                <li>When you provide explicit consent to share.</li>
              </ul>
            </section>

            {/* Section 5 */}
            <section id="pinterest" className="scroll-mt-24 border-t pt-8">
              <h2 className="text-2xl font-bold tracking-tight mb-4 text-foreground">
                5. Pinterest Data Usage
              </h2>
              <div className="rounded-xl bg-muted/40 p-6 border">
                <p className="text-muted-foreground leading-relaxed">
                  PinFlow accesses your Pinterest data through Pinterest&apos;s official API. In doing so, we:
                </p>
                <ul className="list-disc pl-6 mt-4 space-y-2 text-muted-foreground">
                  <li>Only retrieve and write data necessary for automation as configured by you.</li>
                  <li>Never request or access private board or pin information beyond what is authorized.</li>
                  <li>Fully comply with Pinterest&apos;s Developer Terms and Acceptable Use Policy.</li>
                  <li>Store security tokens securely and only for active sessions.</li>
                </ul>
              </div>
            </section>

            {/* Section 6 */}
            <section id="security" className="scroll-mt-24 border-t pt-8">
              <h2 className="text-2xl font-bold tracking-tight mb-4 text-foreground">
                6. Data Security
              </h2>
              <p className="text-muted-foreground leading-relaxed">
                We implement robust technical and organizational security measures to protect your data, including:
              </p>
              <ul className="list-disc pl-6 mt-4 space-y-2 text-muted-foreground">
                <li>Encryption of data in transit (SSL/TLS) and at rest.</li>
                <li>Secure OAuth flow for third-party authorization without saving credentials.</li>
                <li>Regular platform security audits and configuration reviews.</li>
                <li>Restricted access to database nodes, limited to authorized engineers only.</li>
              </ul>
            </section>

            {/* Section 7 */}
            <section id="retention" className="scroll-mt-24 border-t pt-8">
              <h2 className="text-2xl font-bold tracking-tight mb-4 text-foreground">
                7. Data Retention
              </h2>
              <p className="text-muted-foreground leading-relaxed">
                We retain your information only for as long as your account is active or as necessary to provide platform services. If you disconnect your Pinterest account or request account deletion, we will delete your stored API access tokens and configuration parameters.
              </p>
            </section>

            {/* Section 8 */}
            <section id="rights" className="scroll-mt-24 border-t pt-8">
              <h2 className="text-2xl font-bold tracking-tight mb-4 text-foreground">
                8. Your Rights
              </h2>
              <p className="text-muted-foreground leading-relaxed">
                Depending on your location, you may have statutory rights regarding your personal information, which include:
              </p>
              <ul className="list-disc pl-6 mt-4 space-y-2 text-muted-foreground">
                <li>Accessing the personal data we store.</li>
                <li>Correcting inaccurate or incomplete settings.</li>
                <li>Requesting permanent deletion of your data.</li>
                <li>Restricting or objecting to processing of your configurations.</li>
                <li>Data portability (requesting a copy of your scheduled pins).</li>
              </ul>
            </section>

            {/* Section 9 */}
            <section id="third-party" className="scroll-mt-24 border-t pt-8">
              <h2 className="text-2xl font-bold tracking-tight mb-4 text-foreground">
                9. Third-Party Links
              </h2>
              <p className="text-muted-foreground leading-relaxed">
                Our platform may contain links to external web resources (such as Pinterest itself or image databases). We are not responsible for the privacy practices, content, or policies of these external sites. We encourage you to review their privacy statements.
              </p>
            </section>

            {/* Section 10 */}
            <section id="children" className="scroll-mt-24 border-t pt-8">
              <h2 className="text-2xl font-bold tracking-tight mb-4 text-foreground">
                10. Children&apos;s Privacy
              </h2>
              <p className="text-muted-foreground leading-relaxed">
                PinFlow is not directed at or intended for users under the age of 13. We do not knowingly collect, request, or retain personal data from children under 13.
              </p>
            </section>

            {/* Section 11 */}
            <section id="changes" className="scroll-mt-24 border-t pt-8">
              <h2 className="text-2xl font-bold tracking-tight mb-4 text-foreground">
                11. Changes to This Policy
              </h2>
              <p className="text-muted-foreground leading-relaxed">
                We may periodically update this Privacy Policy. Any modifications will be posted directly to this page with an updated &ldquo;Effective Date.&rdquo; Continued use of the service constitutes agreement with the revised policy.
              </p>
            </section>

            {/* Section 12 */}
            <section id="contact" className="scroll-mt-24 border-t pt-8">
              <h2 className="text-2xl font-bold tracking-tight mb-4 text-foreground">
                12. Contact Us
              </h2>
              <p className="text-muted-foreground leading-relaxed">
                If you have any questions or concerns regarding this policy or data deletion, please reach out:
              </p>
              <div className="mt-4 rounded-lg bg-card border p-4 inline-block">
                <p className="text-sm font-semibold text-foreground">WallPeps Support Team</p>
                <p className="text-sm text-muted-foreground mt-1">Email: <a href="mailto:privacy@wallpeps.com" className="text-primary hover:underline">privacy@wallpeps.com</a></p>
              </div>
            </section>

            {/* Section 13 */}
            <section id="compliance" className="scroll-mt-24 border-t pt-8">
              <h2 className="text-2xl font-bold tracking-tight mb-4 text-foreground">
                13. Pinterest Developer Compliance
              </h2>
              <p className="text-muted-foreground leading-relaxed">
                PinFlow operates in strict compliance with Pinterest&apos;s Developer Guidelines and API Terms of Service. Our usage of retrieved Pinterest data is exclusively restricted to the operational delivery of automation features as explicitly authorized by the account holder.
              </p>
            </section>
          </div>
        </article>
      </div>
    </div>
  )
}
