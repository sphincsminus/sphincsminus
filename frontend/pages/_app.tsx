import "../styles/globals.css";
import type { AppProps } from "next/app";
import Link from "next/link";
import { useRouter } from "next/router";

const GITHUB_URL = "https://github.com/sphincsminus/sphincsminus";

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
          <a href={GITHUB_URL} target="_blank" rel="noreferrer">github ↗</a>
        </nav>
      </div>
      <Component {...pageProps} />
      <footer>
        <span>sphincs.fun · 2026 · MIT</span>
        <span>
          <a href={GITHUB_URL} target="_blank" rel="noreferrer">source</a>
          {" · "}
          <a href="https://etherscan.io/address/0x615771e3510a5898b38ab46da2f5b4ef67a2f077" target="_blank" rel="noreferrer">mintgate</a>
          {" · "}
          <a href="https://etherscan.io/address/0x04a4e420aaea469bbf8c2dc909f4d8a1f761b681" target="_blank" rel="noreferrer">token</a>
          {" · "}
          <Link href="/whitepaper">whitepaper</Link>
        </span>
      </footer>
    </main>
  );
}
