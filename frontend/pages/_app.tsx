import "../styles/globals.css";
import type { AppProps } from "next/app";
import Link from "next/link";
import { useRouter } from "next/router";

export default function App({ Component, pageProps }: AppProps) {
  const router = useRouter();
  const tab = (href: string, label: string) => (
    <Link href={href} className={router.pathname === href ? "active" : ""}>
      {label}
    </Link>
  );
  return (
    <main className="wrap">
      <div className="brand-bar">
        <div>
          <div className="brand">sphincs minus</div>
        </div>
        <nav className="tabs">
          {tab("/", "home")}
          {tab("/mint", "mint")}
          {tab("/proof", "proof")}
          {tab("/whitepaper", "whitepaper")}
          {tab("/faq", "faq")}
        </nav>
      </div>
      <Component {...pageProps} />
      <footer>
        <span>sphx.lol · 2026</span>
        <span>
          <a href="https://github.com/vbuterin/sphincsminus" target="_blank" rel="noreferrer">vitalik's repo</a>
          {" · "}
          <Link href="/whitepaper">whitepaper</Link>
        </span>
      </footer>
    </main>
  );
}
