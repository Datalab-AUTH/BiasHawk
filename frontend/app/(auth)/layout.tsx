import Image from "next/image";

/**
 * Half form, half graphic.
 *
 * The panel carries the same dark as the app's sidebar, so signing in already
 * looks like the product rather than a bare form on a grey field. It folds
 * away below `lg`, where a decorative half would just push the form off screen.
 *
 * The wordmark lives here, pinned to the top of the form panel, rather than
 * inside the card , one brand mark per page instead of one per dialog.
 */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      <div className="flex flex-col px-4 py-10">
        <div className="flex items-center gap-3">
          <Image src="/biashawk_logo_icon_dark.svg" alt="" width={40} height={40} priority />
          <span className="text-2xl font-semibold tracking-tight">BiasHawk</span>
        </div>

        <div className="flex flex-1 items-center justify-center">{children}</div>
      </div>

      <aside className="relative hidden overflow-hidden bg-sidebar lg:flex lg:flex-col lg:items-start lg:justify-end">
        <Image
          src="/graphic_wave.webp"
          alt=""
          fill
          priority
          unoptimized
          className="object-cover opacity-90"
        />

        <div className="relative max-w-2xl px-10 pb-20 text-left">
          <p className="text-balance text-xl font-medium leading-snug text-black">
            Assess AI systems for bias, data quality and regulatory risk.
          </p>
          <p className="mt-4 text-balance text-base text-black/70">
            Data governance, fairness metrics, drift, and NIST AI RMF and EU AI Act risk
            assessments, from the documents and datasets you already have.
          </p>
        </div>

        {/* Wordmark is white in the source SVG, and the wave graphic runs
            light in this corner , so it needs its own dark plate to stay
            legible instead of trusting whatever artwork sits behind it. */}
        <a
          href="https://exanta.io"
          target="_blank"
          rel="noopener noreferrer"
          className="absolute bottom-6 right-6 rounded-md bg-black/70 px-2 py-1.5 backdrop-blur-sm"
        >
          <Image
            src="/exanta_logo.svg"
            alt="Exanta"
            width={129}
            height={33}
            className="h-auto w-16"
          />
        </a>
      </aside>
    </div>
  );
}
