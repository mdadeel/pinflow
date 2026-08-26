import Link from "next/link"
import { ThemeToggle } from "@/components/theme-toggle"

const NAV_LINKS = [
  { href: "/", label: "Overview" },
  { href: "/upload", label: "Upload" },
  { href: "/queue", label: "Queue" },
  { href: "/calendar", label: "Calendar" },
] as const

export function Nav() {
  return (
    <header className="border-b">
      <nav className="mx-auto flex max-w-5xl items-center justify-between gap-6 px-6 py-4">
        <Link href="/" className="font-semibold tracking-tight">
          Pinterest Automation
        </Link>
        <ul className="flex items-center gap-1">
          {NAV_LINKS.map(({ href, label }) => (
            <li key={href}>
              <Link
                href={href}
                className="rounded-md px-3 py-1.5 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                {label}
              </Link>
            </li>
          ))}
        </ul>
        <ThemeToggle />
      </nav>
    </header>
  )
}
