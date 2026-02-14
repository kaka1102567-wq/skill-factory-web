import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { ThemeProvider } from "@/components/theme-provider";
import { AuthGate } from "@/components/layout/auth-gate";
import { Sidebar } from "@/components/layout/sidebar";
import "./globals.css";

const inter = Inter({
  subsets: ["latin", "vietnamese"],
  variable: "--font-sans",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "Skill Factory — Build AI Skills",
  description: "Biến raw data thành production-ready AI skills",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi" suppressHydrationWarning>
      <body className={`${inter.variable} ${jetbrainsMono.variable} font-sans antialiased`}>
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem={false}
          disableTransitionOnChange
        >
          <AuthGate>
            <div className="flex min-h-screen bg-background">
              <Sidebar />
              <main className="flex-1 overflow-auto">
                <div className="max-w-6xl mx-auto p-6">
                  {children}
                </div>
              </main>
            </div>
          </AuthGate>
        </ThemeProvider>
      </body>
    </html>
  );
}
