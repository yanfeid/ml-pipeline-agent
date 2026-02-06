"use client";

import { useState, useMemo } from "react";
import { Check, X, Edit3, Save, Trash2, ChevronLeft, ChevronRight, FileCode, Code } from "lucide-react";

interface ComponentVerificationProps {
  components: any[];
  cleanedCode: { [fileName: string]: string };
  repoName: string;
  onSubmit: (verifiedComponents: any[]) => void;
  onCancel: () => void;
}

export function ComponentVerification({
  components,
  cleanedCode,
  repoName,
  onSubmit,
  onCancel,
}: ComponentVerificationProps) {
  const [currentFileIndex, setCurrentFileIndex] = useState(0);
  const [editedComponents, setEditedComponents] = useState<any[]>(
    JSON.parse(JSON.stringify(components))
  );

  // Get total number of files
  const totalFiles = components.length;

  // Get current file's data
  const currentFileComponents = useMemo(() => {
    if (currentFileIndex >= editedComponents.length) return {};
    return editedComponents[currentFileIndex] || {};
  }, [currentFileIndex, editedComponents]);

  // Get file name from current components
  const currentFileName = useMemo(() => {
    const componentNames = Object.keys(currentFileComponents);
    if (componentNames.length === 0) return "Unknown file";

    const firstComponent = currentFileComponents[componentNames[0]];
    return firstComponent?.file_name || "Unknown file";
  }, [currentFileComponents]);

  // Clean file path to show relative path
  const cleanFileName = (filePath: string) => {
    const prefix = `rmr_agent/repos/${repoName}/`;
    if (filePath.startsWith(prefix)) {
      return filePath.slice(prefix.length).replace('.py', '.ipynb');
    }
    return filePath.replace('.py', '.ipynb');
  };

  // Get cleaned code for current file
  const currentCode = useMemo(() => {
    const code = cleanedCode[currentFileName];
    if (!code) return [];

    // Remove line numbers if they exist (format: "1|code")
    const lines = code.split('\n');
    return lines.map(line => {
      const parts = line.split('|');
      return parts.length > 1 ? parts.slice(1).join('|') : line;
    });
  }, [cleanedCode, currentFileName]);

  // Handle component editing
  const handleEditComponent = (componentName: string, field: string, value: any) => {
    setEditedComponents((prev) => {
      const updated = [...prev];
      const fileComponents = { ...updated[currentFileIndex] };

      if (field === "name") {
        // Rename component
        const data = fileComponents[componentName];
        delete fileComponents[componentName];
        fileComponents[value] = data;
      } else {
        // Edit field
        fileComponents[componentName] = {
          ...fileComponents[componentName],
          [field]: value,
        };
      }

      updated[currentFileIndex] = fileComponents;
      return updated;
    });
  };

  // Handle component deletion
  const handleDeleteComponent = (componentName: string) => {
    setEditedComponents((prev) => {
      const updated = [...prev];
      const fileComponents = { ...updated[currentFileIndex] };
      delete fileComponents[componentName];
      updated[currentFileIndex] = fileComponents;
      return updated;
    });
  };

  // Navigation
  const handlePrevious = () => {
    if (currentFileIndex > 0) {
      setCurrentFileIndex(currentFileIndex - 1);
    }
  };

  const handleNext = () => {
    if (currentFileIndex < totalFiles - 1) {
      setCurrentFileIndex(currentFileIndex + 1);
    }
  };

  const handleSubmit = () => {
    onSubmit(editedComponents);
  };

  const componentNames = Object.keys(currentFileComponents);

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Verify ML Components
        </h1>
        <p className="text-gray-600">
          Review components for each file. Verify component names and line ranges by checking the code on the right.
        </p>
      </div>

      {/* File Progress */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <FileCode className="w-5 h-5 text-blue-600" />
            <div>
              <p className="text-sm text-blue-600 font-medium">Current File</p>
              <p className="text-lg font-semibold text-gray-900">
                {cleanFileName(currentFileName)}
              </p>
            </div>
          </div>
          <div className="text-right">
            <p className="text-sm text-gray-500">File Progress</p>
            <p className="text-2xl font-bold text-blue-600">
              {currentFileIndex + 1} / {totalFiles}
            </p>
          </div>
        </div>
      </div>

      {/* Main Content: Two Columns */}
      <div className="grid grid-cols-2 gap-6 mb-6">
        {/* Left Column: Components */}
        <div>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Components in this file
          </h2>

          {componentNames.length === 0 ? (
            <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-6 text-center">
              <p className="text-yellow-800">
                No components identified in this file. You can add components manually or skip to the next file.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {componentNames.map((componentName) => {
                const componentData = currentFileComponents[componentName];
                const [isEditing, setIsEditing] = useState(false);

                return (
                  <div
                    key={componentName}
                    className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden"
                  >
                    <div className="p-4 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
                      <div className="flex items-center gap-3 flex-1">
                        {isEditing ? (
                          <input
                            type="text"
                            value={componentName}
                            onChange={(e) =>
                              handleEditComponent(componentName, "name", e.target.value)
                            }
                            className="flex-1 px-3 py-1 border border-gray-300 rounded-lg text-lg font-semibold focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                            onBlur={() => setIsEditing(false)}
                          />
                        ) : (
                          <h3 className="text-lg font-semibold text-gray-900">
                            {componentName}
                          </h3>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        {isEditing ? (
                          <button
                            onClick={() => setIsEditing(false)}
                            className="p-2 text-green-600 hover:bg-green-50 rounded-lg transition-colors"
                          >
                            <Save className="w-5 h-5" />
                          </button>
                        ) : (
                          <button
                            onClick={() => setIsEditing(true)}
                            className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                          >
                            <Edit3 className="w-5 h-5" />
                          </button>
                        )}
                        <button
                          onClick={() => handleDeleteComponent(componentName)}
                          className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                        >
                          <Trash2 className="w-5 h-5" />
                        </button>
                      </div>
                    </div>

                    <div className="p-4 space-y-3">
                      <div>
                        <label className="text-sm font-medium text-gray-500 mb-1 block">
                          Line Range
                        </label>
                        <input
                          type="text"
                          value={componentData?.line_range || ""}
                          onChange={(e) =>
                            handleEditComponent(componentName, "line_range", e.target.value)
                          }
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                          placeholder="e.g., 1-50"
                        />
                        <p className="text-xs text-gray-500 mt-1">
                          Check the code on the right to verify the line range
                        </p>
                      </div>

                      {componentData?.evidence && componentData.evidence.length > 0 && (
                        <details className="text-sm">
                          <summary className="cursor-pointer text-gray-600 hover:text-gray-900 font-medium">
                            Show Evidence ({componentData.evidence.length})
                          </summary>
                          <ul className="mt-2 space-y-1 pl-3">
                            {componentData.evidence.slice(0, 3).map((e: any, i: number) => (
                              <li
                                key={i}
                                className="text-gray-600 border-l-2 border-gray-200 pl-2"
                              >
                                {e.quote_or_paraphrase || e}
                              </li>
                            ))}
                          </ul>
                        </details>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Tips */}
          <div className="mt-4 bg-gray-50 border border-gray-200 rounded-xl p-4">
            <h4 className="font-semibold text-gray-900 mb-2">💡 Tips</h4>
            <ul className="text-sm text-gray-600 space-y-1">
              <li>• Verify line ranges don't overlap</li>
              <li>• Check the code display to ensure correct boundaries</li>
              <li>• Delete components that aren't separate ML steps</li>
              <li>• Component names should describe their ML function</li>
            </ul>
          </div>
        </div>

        {/* Right Column: Code Display */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
              <Code className="w-5 h-5" />
              Cleaned Code
            </h2>
            <span className="text-sm text-gray-500">
              {currentCode.length} lines
            </span>
          </div>

          <div className="bg-gray-900 rounded-xl overflow-hidden" style={{ height: "600px" }}>
            {currentCode.length > 0 ? (
              <div className="h-full overflow-auto">
                <pre className="p-4 text-sm font-mono">
                  {currentCode.map((line, i) => (
                    <div key={i} className="flex">
                      <span className="text-gray-500 select-none w-12 text-right pr-4">
                        {i + 1}
                      </span>
                      <code className="text-gray-100 flex-1">{line}</code>
                    </div>
                  ))}
                </pre>
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-gray-500">
                <div className="text-center">
                  <Code className="w-12 h-12 mx-auto mb-2 opacity-50" />
                  <p>No code available for this file</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Navigation and Actions */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={handlePrevious}
            disabled={currentFileIndex === 0}
            className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          >
            <ChevronLeft className="w-4 h-4" />
            Previous
          </button>
          <button
            onClick={handleNext}
            disabled={currentFileIndex >= totalFiles - 1}
            className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          >
            Next
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={onCancel}
            className="px-6 py-3 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors flex items-center gap-2"
          >
            <X className="w-5 h-5" />
            Cancel
          </button>
          {currentFileIndex === totalFiles - 1 ? (
            <button
              onClick={handleSubmit}
              className="px-8 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors flex items-center gap-2"
            >
              <Check className="w-5 h-5" />
              Submit All Components
            </button>
          ) : (
            <button
              onClick={handleNext}
              className="px-8 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors flex items-center gap-2"
            >
              Next File
              <ChevronRight className="w-5 h-5" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
