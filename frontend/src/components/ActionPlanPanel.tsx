import React, { useState } from "react";
import { forestApi } from "../utils/forestApi";
import type { ActionPlanRequest } from "../utils/forestApi";

interface ActionPlanPanelProps {
    metrics: ActionPlanRequest | null;
}

export const ActionPlanPanel: React.FC<ActionPlanPanelProps> = ({ metrics }) => {
    const [loading, setLoading] = useState(false);
    const [markdownResponse, setMarkdownResponse] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const handleGenerate = async () => {
        if (!metrics) return;
        setLoading(true);
        setError(null);
        try {
            const result = await forestApi.getActionPlan(metrics);
            setMarkdownResponse(result.guidelines_markdown);
        } catch (err: any) {
            setError(err.message || "Failed to generate action plan. Is your API key configured?");
        } finally {
            setLoading(false);
        }
    };

    if (!metrics) return null;

    return (
        <div className="bg-white p-4 rounded-lg shadow-md border border-gray-200 mt-4">
            <h3 className="text-xl font-bold mb-2">AI Forest Officer Guidelines</h3>
            <p className="text-sm text-gray-600 mb-4">
                Generate an actionable set of steps to maintain or improve this region's health, powered by Google Gemini.
            </p>

            {!markdownResponse && (
                <button
                    onClick={handleGenerate}
                    disabled={loading}
                    className="bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 disabled:opacity-50 transition-colors"
                >
                    {loading ? "Generating Plan..." : "Generate AI Action Plan"}
                </button>
            )}

            {error && (
                <div className="mt-4 p-3 bg-red-100 text-red-800 border border-red-200 rounded text-sm">
                    {error}
                </div>
            )}

            {markdownResponse && (
                <div className="mt-4 pt-4 border-t border-gray-200">
                    <h4 className="font-semibold text-lg mb-2">Recommended Actions:</h4>
                    <div className="prose prose-sm max-w-none text-gray-800 whitespace-pre-wrap font-sans">
                        {markdownResponse}
                    </div>
                    <button
                        onClick={() => setMarkdownResponse(null)}
                        className="mt-4 text-sm text-green-600 hover:underline"
                    >
                        Clear Plan
                    </button>
                </div>
            )}
        </div>
    );
};
