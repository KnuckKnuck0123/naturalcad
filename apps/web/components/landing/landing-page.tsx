import Link from "next/link";

import { Topbar } from "@/components/chrome/topbar";

export function LandingPage() {
  return (
    <main className="shell shell--landing">
      <div className="screen-frame">
        <Topbar brand="NATURALCAD" status="PROMPT-DRIVEN CAD" />

        <section className="landing-minimal">
          <div className="landing-minimal__inner">
            <p className="eyebrow">Prompt to CAD</p>
            <div className="hero-mark hero-mark--minimal">
              <span className="hero-mark__prefix">natural</span>
              <h1>CAD</h1>
            </div>
            <p className="lede lede--minimal">
              NaturalCAD is a prompt-driven CAD workspace for turning plain language into buildable geometry.
            </p>

            <div className="hero-actions hero-actions--minimal">
              <Link href="/app" className="button button--primary">
                Start Modeling
              </Link>
            </div>
          </div>

          <div className="landing-minimal__footer">
            <span>Prompt</span>
            <span>Generate</span>
            <span>Iterate</span>
            <span>Export</span>
          </div>
          <nav className="legal-footer">
            <Link href="/terms">Terms</Link>
            <Link href="/privacy">Privacy</Link>
            <span>Beta</span>
          </nav>
        </section>
      </div>
    </main>
  );
}
