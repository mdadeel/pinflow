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
  title: "PinFlow",
  description: "Automate your Pinterest workflow with AI-powered pin generation and scheduling",
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
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <ThemeProvider>
          <Nav />
          <main className="flex-1">{children}</main>
        </ThemeProvider>
      </body>
    </html>
  )
}