"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ComponentType } from "react";
import type { ResultData } from "../lib/model";

type StoryComponent = ComponentType<{ results: ResultData }>;

export default function LazyStory() {
  const anchor = useRef<HTMLDivElement>(null);
  const started = useRef(false);
  const [story, setStory] = useState<{ Component: StoryComponent; results: ResultData } | null>(null);
  const [error, setError] = useState(false);
  const load = useCallback(async () => {
    if (started.current) return;
    started.current = true;
    try {
      const [module, response] = await Promise.all([import("./story"), fetch("/data/results.json")]);
      if (!response.ok) throw new Error(`Data request failed: ${response.status}`);
      setStory({ Component: module.default, results: await response.json() as ResultData });
    } catch {
      started.current = false;
      setError(true);
    }
  }, []);
  useEffect(() => {
    if (location.hash && location.hash !== "#top") void load();
    const onHash = () => { if (location.hash && location.hash !== "#top") void load(); };
    window.addEventListener("hashchange", onHash);
    const observer = new IntersectionObserver((entries) => { if (entries[0]?.isIntersecting) void load(); });
    if (anchor.current) observer.observe(anchor.current);
    return () => { observer.disconnect(); window.removeEventListener("hashchange", onHash); };
  }, [load]);
  useEffect(() => { if (story && location.hash && location.hash !== "#top") document.getElementById(location.hash.slice(1))?.scrollIntoView(); }, [story]);
  return <div ref={anchor}>{story ? <story.Component results={story.results} /> : error ? <div className="load-state" role="alert">The analysis data could not load. <button type="button" onClick={() => { setError(false); void load(); }}>Try again</button></div> : <div className="load-state" aria-live="polite">Scroll to explore the data and model.</div>}</div>;
}
