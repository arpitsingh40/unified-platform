import "./globals.css";
import Header from "@/components/Header";

export const metadata = {
  title: "DRIFT — Fast Fashion. New Drops Weekly.",
  description: "DRIFT: New drops weekly. Gone forever. ₹599–₹1,999. Free shipping over ₹1,999. Cash on delivery.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-[#FFF8F0] text-[#0a0a0a] antialiased">
        <div className="bg-black text-white text-center text-xs tracking-[0.18em] py-2">
          NEW DROP LIVE — FREE SHIPPING OVER ₹1,999 • COD AVAILABLE • 48H DISPATCH
        </div>
        <Header />
        <main>{children}</main>
        <footer className="mt-16 border-t border-black/10 bg-white">
          <div className="mx-auto max-w-[1280px] px-4 py-10 grid md:grid-cols-4 gap-8 text-sm">
            <div>
              <div className="font-black tracking-[0.2em] text-lg">DRIFT</div>
              <p className="mt-2 text-black/60">New drops weekly. Limited run. Once gone, never restocked. Fast fashion with a conscience — 48h dispatch, easy returns.</p>
            </div>
            <div>
              <div className="font-semibold">Shop</div>
              <div className="mt-2 space-y-1 text-black/60"><a href="/catalog">New In</a> • <a href="/catalog?cat=Dresses">Dresses</a> • <a href="/catalog?cat=Tops">Tops</a></div>
            </div>
            <div>
              <div className="font-semibold">Help</div>
              <div className="mt-2 space-y-1 text-black/60">Shipping • Returns (14 days) • Size Guide • Contact</div>
            </div>
            <div>
              <div className="font-semibold">Worth</div>
              <div className="mt-2 text-black/60">AUM-style dashboard: Orders,Revenue,CAC,LTV. Owner sees it in <a className="underline" href="/admin">/admin</a>.</div>
            </div>
          </div>
          <div className="border-t py-4 text-center text-xs text-black/40">© 2026 DRIFT • Built as a Worth-Creating Business • <span className="font-mono">BusinessFactory</span></div>
        </footer>
      </body>
    </html>
  );
}
