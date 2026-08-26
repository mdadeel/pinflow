import "./globals.css"
import { Geist, Geist_Mono } from "next/font/google"
import type { Metadata } from "next"

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
})

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
})

export const metadata: Metadata = {
  title: "Pinterest Automation",
  description: "Automate Pinterest pins with AI",
}

import type { ReactNode } from "react"
import { Nav } from "@/components/nav"
import { ThemeProvider } from "@/components/theme-provider"

export default function RootLayout({
  children,
}: {
  children: ReactNode
}) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <ThemeProvider>
          <Nav />
        </ThemeProvider>
        <main className="flex-1">{children}</main>
      </body>
    </html>
  )
}