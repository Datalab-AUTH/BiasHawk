"use client";

import { useEffect, useState } from "react";
import { Download, FileText } from "lucide-react";
import { remark } from "remark";
import remarkGfm from "remark-gfm";
import remarkHtml from "remark-html";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { EmptyState, Spinner } from "@/components/ui/primitives";

/**
 * Render a Markdown report.
 *
 * Reports come from the model as Markdown; remark converts them once per change
 * rather than on every render. Wide tables get their own scroll container so the
 * page itself never scrolls sideways.
 */
export function ReportView({
  markdown,
  pdfPath,
  downloads,
  emptyTitle,
  emptyDescription,
}: {
  markdown: string;
  /** Shorthand for a single download. */
  pdfPath?: string;
  /**
   * Every document behind this view, when one analysis produces more than
   * one. Anything the API can render should be reachable from the screen
   * that shows it, not only the one the page happens to display.
   */
  downloads?: { label: string; path: string }[];
  emptyTitle: string;
  emptyDescription?: string;
}) {
  const [html, setHtml] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!markdown?.trim()) {
      setHtml(null);
      return;
    }
    void remark()
      .use(remarkGfm)
      .use(remarkHtml, { sanitize: false })
      .process(markdown)
      .then((file) => {
        if (!cancelled) {
          setHtml(
            String(file).replace(
              /<table>/g,
              '<div class="table-scroll"><table>'
            ).replace(/<\/table>/g, "</table></div>")
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [markdown]);

  if (!markdown?.trim()) {
    return <EmptyState icon={FileText} title={emptyTitle} description={emptyDescription} />;
  }

  const links = downloads ?? (pdfPath ? [{ label: "Download PDF", path: pdfPath }] : []);

  return (
    <div className="flex flex-col gap-4">
      {links.length ? (
        <div className="flex flex-wrap justify-end gap-2">
          {links.map((link) => (
            <Button key={link.path} asChild size="sm" variant="outline">
              <a href={api.url(link.path)} target="_blank" rel="noreferrer">
                <Download />
                {link.label}
              </a>
            </Button>
          ))}
        </div>
      ) : null}

      {html === null ? (
        <Spinner className="text-muted-foreground" />
      ) : (
        <article className="prose-report" dangerouslySetInnerHTML={{ __html: html }} />
      )}
    </div>
  );
}
