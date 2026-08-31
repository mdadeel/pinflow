"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { ThemeToggle } from "@/components/theme-toggle"
import { SearchBar } from "@/components/search-bar"

const SECTION_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/upload", label: "Upload" },
  { href: "/queue", label: "Queue" },
  { href: "/exports", label: "Exports" },
  { href: "/settings", label: "Settings" },
  { href: "/errors", label: "Errors" },
  { href: "/calendar", label: "Calendar" },
  { href: "/gallery", label: "Gallery" },
] as const

const isSectionPath = (pathname: string | null) =>
  pathname?.startsWith("/dashboard") && pathname !== "/dashboard" ||
  (!!pathname && SECTION_LINKS.some((l) => pathname === l.href))

function UserAvatar() {
  const pathname = usePathname()
  const [initial, setInitial] = useState("U")

  useEffect(() => {
    const name = localStorage.getItem("user_name")
    if (name?.trim()) setInitial(name.trim().charAt(0).toUpperCase())

    const handleStorage = () => {
      const updated = localStorage.getItem("user_name")
      if (updated?.trim()) setInitial(updated.trim().charAt(0).toUpperCase())
      else setInitial("U")
    }
    window.addEventListener("storage", handleStorage)
    return () => window.removeEventListener("storage", handleStorage)
  }, [])

  return (
    <Link
      href="/profile"
      className={`flex h-9 w-9 items-center justify-center rounded-full text-sm font-bold transition-colors ${
        pathname === "/profile"
          ? "bg-primary text-primary-foreground"
          : "bg-primary/10 text-primary hover:bg-primary/20"
      }`}
    >
      {initial}
    </Link>
  )
}

export function Nav() {
  const pathname = usePathname()
  const showSections = isSectionPath(pathname) || pathname === "/dashboard"

  return (
    <header className="sticky top-0 z-50 border-b bg-background/80 backdrop-blur-md">
      <nav className="flex w-full items-center justify-between gap-6 px-6 py-3">
        <Link href="/" className="flex items-center gap-2 font-bold tracking-tight">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 0C5.373 0 0 5.373 0 12c0 5.084 3.163 9.426 7.627 11.174-.105-.949-.2-2.405.042-3.441.218-.937 1.407-5.965 1.407-5.965s-.359-.719-.359-1.782c0-1.668.967-2.914 2.171-2.914 1.023 0 1.518.769 1.518 1.69 0 1.029-.655 2.568-.994 3.995-.283 1.194.599 2.169 1.777 2.169 2.133 0 3.772-2.249 3.772-5.495 0-2.873-2.064-4.882-5.012-4.882-3.414 0-5.418 2.561-5.418 5.207 0 1.031.397 2.138.893 2.738a.36.36 0 01.083.345l-.333 1.36c-.053.22-.174.267-.402.161-1.499-.698-2.436-2.889-2.436-4.649 0-3.785 2.75-7.262 7.929-7.262 4.163 0 7.398 2.967 7.398 6.931 0 4.136-2.607 7.464-6.227 7.464-1.216 0-2.359-.631-2.75-1.378l-.748 2.853c-.271 1.043-1.002 2.35-1.492 3.146C9.57 23.812 10.763 24 12 24c6.627 0 12-5.373 12-12S18.627 0 12 0z" />
            </svg>
          </span>
          PinFlow
        </Link>

        <ul className="flex items-center gap-1 flex-wrap py-0.5">
          {showSections &&
            SECTION_LINKS.map(({ href, label }) => (
              <li key={href}>
                <Link
                  href={href}
                  className={`relative rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                    pathname === href
                      ? "text-primary"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {label}
                  {pathname === href && (
                    <span className="absolute bottom-0 left-3 right-3 h-0.5 rounded-full bg-primary" />
                  )}
                </Link>
              </li>
            ))}
        </ul>

        <div className="flex items-center gap-2">
          {pathname !== "/" && <SearchBar />}
          {pathname === "/" && (
            <Link
              href="/dashboard"
              className="inline-flex h-9 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
            >
              Dashboard
            </Link>
          )}
          <UserAvatar />
          <ThemeToggle />
        </div>
      </nav>
    </header>
  )
}
