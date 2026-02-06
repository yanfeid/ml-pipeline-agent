"use client";

import { useEffect, useRef, useState } from "react";
import { CheckCircle2, ExternalLink, RotateCcw, GitPullRequest, ChevronDown, ChevronUp } from "lucide-react";

interface ResultsPageProps {
  prUrl: string;
  prBody: string;
  repoName: string;
  runId: string;
  onReset: () => void;
}

export function ResultsPage({ prUrl, prBody, repoName, runId, onReset }: ResultsPageProps) {
  const [mermaidExpanded, setMermaidExpanded] = useState(true);
  const mermaidRef = useRef<HTMLDivElement>(null);

  // Extract mermaid diagram from PR body
  const extractMermaid = (body: string): string | null => {
    const mermaidPattern = /```mermaid\n([\s\S]*?)\n```/;
    const match = body.match(mermaidPattern);
    return match ? match[1].trim() : null;
  };

  // Split PR body into sections
  const parsePrBody = (body: string) => {
    const mermaidCode = extractMermaid(body);

    if (!mermaidCode) {
      return { beforeMermaid: body, mermaidCode: null, afterMermaid: "" };
    }

    const mermaidPattern = /```mermaid\n[\s\S]*?\n```/;
    const parts = body.split(mermaidPattern);

    return {
      beforeMermaid: parts[0]?.trim() || "",
      mermaidCode,
      afterMermaid: parts[1]?.trim() || ""
    };
  };

  const { beforeMermaid, mermaidCode, afterMermaid } = parsePrBody(prBody);

  // Render Mermaid using mermaid.js
  useEffect(() => {
    if (mermaidCode && mermaidRef.current) {
      // Dynamically load mermaid
      const loadMermaid = async () => {
        try {
          // Use CDN version of mermaid
          const script = document.createElement('script');
          script.src = 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js';
          script.async = true;

          script.onload = () => {
            // @ts-ignore
            if (window.mermaid) {
              // @ts-ignore
              window.mermaid.initialize({
                startOnLoad: false,
                theme: 'default',
                flowchart: {
                  useMaxWidth: true,
                  htmlLabels: true,
                  curve: 'basis'
                }
              });

              // @ts-ignore
              window.mermaid.render('mermaid-diagram', mermaidCode).then((result: any) => {
                if (mermaidRef.current) {
                  mermaidRef.current.innerHTML = result.svg;
                }
              }).catch((err: any) => {
                console.error('Mermaid render error:', err);
                if (mermaidRef.current) {
                  mermaidRef.current.innerHTML = `<pre class="text-red-600 text-sm">${mermaidCode}</pre>`;
                }
              });
            }
          };

          document.head.appendChild(script);
        } catch (err) {
          console.error('Failed to load mermaid:', err);
        }
      };

      loadMermaid();
    }
  }, [mermaidCode]);

  // Render markdown-like text
  const renderMarkdown = (text: string) => {
    if (!text) return null;

    // Simple markdown rendering
    const lines = text.split('\n');
    return lines.map((line, i) => {
      // Headers
      if (line.startsWith('###')) {
        return <h3 key={i} className="text-xl font-bold text-gray-900 mt-6 mb-3">{line.slice(3).trim()}</h3>;
      }
      if (line.startsWith('##')) {
        return <h2 key={i} className="text-2xl font-bold text-gray-900 mt-8 mb-4">{line.slice(2).trim()}</h2>;
      }
      if (line.startsWith('#')) {
        return <h1 key={i} className="text-3xl font-bold text-gray-900 mt-8 mb-4">{line.slice(1).trim()}</h1>;
      }

      // Bullet points
      if (line.trim().startsWith('- ') || line.trim().startsWith('* ')) {
        return (
          <li key={i} className="ml-6 text-gray-700 mb-2">
            {line.trim().slice(2)}
          </li>
        );
      }

      // Code blocks
      if (line.trim().startsWith('`') && line.trim().endsWith('`')) {
        const code = line.trim().slice(1, -1);
        return (
          <code key={i} className="bg-gray-100 px-2 py-1 rounded text-sm font-mono text-gray-800">
            {code}
          </code>
        );
      }

      // Links
      const linkPattern = /\[([^\]]+)\]\(([^)]+)\)/g;
      if (linkPattern.test(line)) {
        const parts = line.split(linkPattern);
        return (
          <p key={i} className="text-gray-700 mb-3">
            {parts.map((part, j) => {
              if (j % 3 === 0) return part;
              if (j % 3 === 1) {
                const url = parts[j + 1];
                return (
                  <a
                    key={j}
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline"
                  >
                    {part}
                  </a>
                );
              }
              return null;
            })}
          </p>
        );
      }

      // Bold text
      const boldPattern = /\*\*([^*]+)\*\*/g;
      if (boldPattern.test(line)) {
        const parts = line.split(boldPattern);
        return (
          <p key={i} className="text-gray-700 mb-3">
            {parts.map((part, j) =>
              j % 2 === 1 ? <strong key={j}>{part}</strong> : part
            )}
          </p>
        );
      }

      // Empty line
      if (!line.trim()) {
        return <div key={i} className="h-2" />;
      }

      // Regular paragraph
      return <p key={i} className="text-gray-700 mb-3">{line}</p>;
    });
  };

  return (
    <div className="max-w-5xl mx-auto">
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8 mb-6">
        {/* Success Header */}
        <div className="text-center mb-8">
          <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <CheckCircle2 className="w-10 h-10 text-green-600" />
          </div>

          <h1 className="text-3xl font-bold text-gray-900 mb-3">
            Workflow Complete!
          </h1>
          <p className="text-gray-600 mb-6">
            Your ML pipeline has been successfully refactored and a pull request has been created.
          </p>

          {/* PR Link */}
          {prUrl && (
            <a
              href={prUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-3 px-8 py-4 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl font-semibold text-lg hover:from-blue-700 hover:to-purple-700 transition-all shadow-lg"
            >
              <GitPullRequest className="w-6 h-6" />
              View Pull Request
              <ExternalLink className="w-5 h-5" />
            </a>
          )}
        </div>

        {/* Run Info */}
        <div className="bg-gray-50 rounded-xl p-4 mb-8">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-500">Repository</span>
              <p className="font-medium text-gray-900">{repoName}</p>
            </div>
            <div>
              <span className="text-gray-500">Run ID</span>
              <p className="font-medium text-gray-900">{runId}</p>
            </div>
          </div>
        </div>

        {/* PR Body Content */}
        {prBody && (
          <div className="prose max-w-none">
            {/* Before Mermaid */}
            {beforeMermaid && (
              <div className="mb-6">
                {renderMarkdown(beforeMermaid)}
              </div>
            )}

            {/* Mermaid Diagram */}
            {mermaidCode && (
              <div className="bg-gray-50 rounded-xl border border-gray-200 overflow-hidden mb-6">
                <button
                  onClick={() => setMermaidExpanded(!mermaidExpanded)}
                  className="w-full px-6 py-4 flex items-center justify-between bg-white border-b border-gray-200 hover:bg-gray-50 transition-colors"
                >
                  <span className="font-semibold text-gray-900">View ML Pipeline</span>
                  {mermaidExpanded ? (
                    <ChevronUp className="w-5 h-5 text-gray-500" />
                  ) : (
                    <ChevronDown className="w-5 h-5 text-gray-500" />
                  )}
                </button>
                {mermaidExpanded && (
                  <div className="p-6 bg-white">
                    <div
                      ref={mermaidRef}
                      className="flex items-center justify-center overflow-x-auto"
                    >
                      <div className="text-gray-400 text-sm">Loading diagram...</div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* After Mermaid */}
            {afterMermaid && (
              <div className="mb-6">
                {renderMarkdown(afterMermaid)}
              </div>
            )}

            {/* Fallback: Show raw PR body if no parsing */}
            {!mermaidCode && !beforeMermaid && (
              <div className="bg-gray-50 rounded-xl p-6">
                <pre className="whitespace-pre-wrap text-sm text-gray-700 font-mono">
                  {prBody}
                </pre>
              </div>
            )}
          </div>
        )}

        {/* Generated Files Summary */}
        <div className="bg-gradient-to-br from-blue-50 to-purple-50 rounded-xl p-6 mt-8">
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-green-600" />
            Generated Files
          </h3>
          <ul className="grid grid-cols-2 gap-3 text-sm">
            <li className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0" />
              <code className="bg-white px-2 py-1 rounded text-xs font-mono">config/environment.ini</code>
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0" />
              <code className="bg-white px-2 py-1 rounded text-xs font-mono">config/solution.ini</code>
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0" />
              <code className="bg-white px-2 py-1 rounded text-xs font-mono">notebooks/*.ipynb</code>
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0" />
              <code className="bg-white px-2 py-1 rounded text-xs font-mono">rmr_agent_results.md</code>
            </li>
          </ul>
        </div>

        {/* Start New Button */}
        <div className="text-center mt-8">
          <button
            onClick={onReset}
            className="inline-flex items-center gap-2 px-6 py-3 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors"
          >
            <RotateCcw className="w-5 h-5" />
            Start New Workflow
          </button>
        </div>
      </div>
    </div>
  );
}
