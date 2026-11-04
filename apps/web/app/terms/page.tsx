export const metadata = {
  title: "Terms of Service - NaturalCAD",
};

export default function TermsPage() {
  return (
    <main className="shell shell--legal">
      <div className="legal-content">
        <h1>Terms of Service</h1>
        <p className="legal-date">Last updated: July 12, 2026</p>

        <p>
          NaturalCAD is an experimental beta service that turns natural language prompts
          and reference images into CAD geometry using generative models and open-source
          geometry libraries. By using the service you accept these terms. If you do not
          agree, please do not use NaturalCAD.
        </p>

        <h2>Beta disclaimer</h2>
        <p>
          This is a public beta. Outputs may be inaccurate, incomplete, or unsuitable for
          fabrication. Always verify dimensions, clearances, and fits before manufacturing.
          CAD files are provided as-is without warranty of any kind.
        </p>

        <h2>Acceptable use</h2>
        <p>
          You may use NaturalCAD only for lawful purposes and in compliance with any
          applicable export, manufacturing, or intellectual-property laws. Do not attempt to
          abuse the free tier, bypass rate limits, or use the service to generate malicious,
          infringing, or harmful content.
        </p>

        <h2>Your content</h2>
        <p>
          You retain ownership of prompts and images you submit. We process them to generate
          geometry and store them only as long as necessary to operate the service. Uploaded
          images are sanitized, stripped of metadata, and stored with access limited to your
          session.
        </p>

        <h2>AI-generated outputs</h2>
        <p>
          Generated geometry, code, and summaries are produced by third-party language
          models and may not be unique. We do not claim ownership of outputs, but we also
          cannot guarantee they do not resemble existing works or meet your specific
          engineering requirements.
        </p>

        <h2>Usage limits</h2>
        <p>
          Free beta access is rate-limited per network and per session. We may change,
          suspend, or terminate access at any time. A kill switch can be activated to pause
          generations immediately during abuse or unexpected cost spikes.
        </p>

        <h2>No warranty</h2>
        <p>
          NaturalCAD is provided “as is” without warranties of merchantability, fitness for
          a particular purpose, or non-infringement. We are not liable for damages arising
          from use of generated files or reliance on generated geometry.
        </p>

        <h2>Changes</h2>
        <p>
          We may update these terms as the beta evolves. Continued use after changes means
          you accept the revised terms.
        </p>

        <h2>Contact</h2>
        <p>
          Questions or concerns: support@naturalcad.io
        </p>
      </div>
    </main>
  );
}
