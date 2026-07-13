export const metadata = {
  title: "Privacy Policy - NaturalCAD",
};

export default function PrivacyPage() {
  return (
    <main className="shell shell--legal">
      <div className="legal-content">
        <h1>Privacy Policy</h1>
        <p className="legal-date">Last updated: July 12, 2026</p>

        <p>
          This policy describes what NaturalCAD collects, how we use it, and how long we
          keep it during the public beta.
        </p>

        <h2>What we collect</h2>
        <ul>
          <li>
            <strong>Session identifier.</strong> A random guest session id stored in an
            httpOnly cookie so we can associate projects, runs, and uploads with your
            browser.
          </li>
          <li>
            <strong>Prompts and messages.</strong> Text you enter to describe parts or
            refine geometry.
          </li>
          <li>
            <strong>Reference images.</strong> Images you upload to guide generation.
          </li>
          <li>
            <strong>Generated artifacts.</strong> CAD files (STEP, STL, GLB, DXF) and the
            code used to produce them.
          </li>
          <li>
            <strong>Hashed IP addresses.</strong> A one-way hash of your network address is
            used for rate-limiting; the raw address is not retained.
          </li>
          <li>
            <strong>Usage telemetry.</strong> Token counts, model names, run status, and
            latency to enforce limits and debug failures.
          </li>
        </ul>

        <h2>How we use it</h2>
        <ul>
          <li>To generate, iterate, and export CAD geometry.</li>
          <li>To enforce rate limits and prevent abuse.</li>
          <li>To diagnose errors and improve generation quality.</li>
        </ul>

        <h2>Model providers</h2>
        <p>
          Prompts and images are sent to language-model providers via OpenRouter so the
          service can interpret requests and generate build123d code. Provider handling is
          governed by OpenRouter’s and the underlying model providers’ privacy policies.
        </p>

        <h2>Image handling</h2>
        <p>
          Uploaded images are validated, stripped of EXIF and other metadata, downscaled if
          large, and stored privately under your session. They are not used to train models.
        </p>

        <h2>Retention</h2>
        <p>
          Sessions and attachments expire automatically after inactivity. Generated
          artifacts and project history remain associated with your session until you delete
          them or the beta ends.
        </p>

        <h2>Your choices</h2>
        <p>
          You can clear your browser cookies to end a guest session. Clearing cookies does
          not delete server-side project data, but without the session id that data is no
          longer linked to you.
        </p>

        <h2>Changes</h2>
        <p>
          This policy may change as the product evolves. The latest version will always be
          available at this URL.
        </p>

        <h2>Contact</h2>
        <p>
          Privacy questions: privacy@naturalcad.io
        </p>
      </div>
    </main>
  );
}
