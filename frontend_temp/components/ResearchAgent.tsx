'use client';

import { useEffect, useState, useCallback } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Person {
  id: number;
  full_name: string;
  email: string;
  title: string;
  company_id: number;
  created_at: string;
}

interface Company {
  id: number;
  name: string;
  domain: string;
  campaign_id: number;
  created_at: string;
}

interface Progress {
  percent: number;
  msg: string;
  query?: string;
  found_fields?: string[];
  research_mode?: string;
}

interface ContextSnippet {
  id: number;
  entity_type: string;
  entity_id: number;
  snippet_type: string;
  content: string;
  payload: Record<string, string>;
  source_urls: string[];
  created_at: string;
}

export default function ResearchAgent() {
  const [people, setPeople] = useState<Person[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [results, setResults] = useState<ContextSnippet[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [currentCompanyId, setCurrentCompanyId] = useState<number | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');

  useEffect(() => {
    fetchPeople();
    fetchCompanies();
    checkSystemHealth();
  }, []);

  useEffect(() => {
    const websocket = new WebSocket(`ws://localhost:8000/ws`);
    
    websocket.onopen = () => {
      console.log('WebSocket connected');
      setConnectionStatus('connected');
      addLog('Connected to Alpha Research Agent');
    };

    websocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        setProgress(data);
        
        if (data.company_id && !currentCompanyId) {
          setCurrentCompanyId(data.company_id);
          addLog(`Company ID set to: ${data.company_id}`);
        }
        
        addLog(`${data.msg} (${data.percent}% complete)`);
        
        if (data.query) {
          addLog(`Query: "${data.query}"`);
        }
        
        if (data.found_fields && data.found_fields.length > 0) {
          addLog(`Fields completed: ${data.found_fields.join(', ')}`);
        }
        
        if (data.percent >= 100 && data.msg.includes('completed')) {
          addLog('Research completed - fetching results...');
          
          setTimeout(() => {
            const targetCompanyId = currentCompanyId || data.company_id;
            if (targetCompanyId) {
              addLog(`Fetching results for company ID: ${targetCompanyId}`);
              fetchResults(targetCompanyId);
            } else {
              addLog('No company ID available to fetch results');
            }
            setProgress(null);
            setIsLoading(false);
          }, 2000);
        }
        
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err);
        addLog('WebSocket message parsing error');
      }
    };

    websocket.onerror = (error) => {
      console.error('WebSocket error:', error);
      setConnectionStatus('disconnected');
      setError('WebSocket connection failed - research updates unavailable');
      addLog('WebSocket connection error');
    };

    websocket.onclose = () => {
      console.log('WebSocket disconnected');
      setConnectionStatus('disconnected');
      addLog('Disconnected from research agent');
    };

    setWs(websocket);

    return () => {
      websocket.close();
    };
  }, [currentCompanyId]);

  const addLog = useCallback((message: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prev => [...prev.slice(-24), `[${timestamp}] ${message}`]);
  }, []);

  const checkSystemHealth = async () => {
    try {
      addLog('Checking system health...');
      const response = await fetch(`${API_BASE}/health`);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const health = await response.json();
      addLog(`System Health: ${health.status}`);
      addLog(`Redis: ${health.redis}, DB: ${health.database}`);
      
      if (health.worker_queue !== undefined) {
        addLog(`Queue has ${health.worker_queue} jobs`);
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      addLog(`Health check failed: ${errorMsg}`);
      console.error('Health check error:', err);
    }
  };

  const fetchPeople = async () => {
    try {
      addLog('Loading research targets...');
      const response = await fetch(`${API_BASE}/people`);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      setPeople(data);
      addLog(`Loaded ${data.length} research targets`);
      
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      setError(`Failed to load people data: ${errorMsg}`);
      addLog(`Failed to load research targets: ${errorMsg}`);
    }
  };

  const fetchCompanies = async () => {
    try {
      addLog('Loading companies...');
      const response = await fetch(`${API_BASE}/companies`);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      setCompanies(data);
      addLog(`Loaded ${data.length} companies`);
      
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      setError(`Failed to load companies data: ${errorMsg}`);
      addLog(`Failed to load companies: ${errorMsg}`);
    }
  };

  const debugDatabase = async () => {
    try {
      addLog('Running database debug check...');
      
      const response = await fetch(`${API_BASE}/debug/db`);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const debug = await response.json();
      
      if (debug.status === 'error') {
        addLog(`Database Error: ${debug.error}`);
        return;
      }
      
      addLog(`Database Status: ${debug.status}`);
      addLog(`Record counts:`);
      Object.entries(debug.record_counts).forEach(([table, count]) => {
        addLog(`   - ${table}: ${count}`);
      });
      
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      addLog(`Database debug failed: ${errorMsg}`);
    }
  };

  const fetchResults = async (companyId?: number) => {
    const targetCompanyId = companyId || currentCompanyId;
    
    if (!targetCompanyId) {
      addLog('No company ID specified to fetch results');
      setResults([]);
      return;
    }
    
    try {
      addLog(`Fetching context snippets for company ID: ${targetCompanyId}`);
      
      const response = await fetch(`${API_BASE}/snippets/${targetCompanyId}`);
      
      if (!response.ok) {
        if (response.status === 404) {
          addLog(`No context snippets found for company ${targetCompanyId}`);
          addLog(`Try running research first to generate data`);
          setResults([]);
          return;
        } else {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
      }
      
      const data = await response.json();
      
      if (data && data.length > 0) {
        setResults(data);
        
        const realSnippets = data.filter((s: ContextSnippet) => s.snippet_type === 'real_ai_research');
        const totalUrls = data.reduce((acc: number, s: ContextSnippet) => acc + (s.source_urls?.length || 0), 0);
        
        addLog(`Loaded ${data.length} context snippets`);
        addLog(`Real AI research: ${realSnippets.length}, Web sources: ${totalUrls}`);
        
      } else {
        addLog('No context snippets found for this company');
        setResults([]);
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      setError(`Failed to load context snippets: ${errorMsg}`);
      addLog(`Failed to load context snippets: ${errorMsg}`);
    }
  };

  const runResearch = async (personId: number, personName: string) => {
    setIsLoading(true);
    setError(null);
    setResults([]);
    setProgress({ percent: 0, msg: 'Initializing research agent...', research_mode: 'REAL_SEARCH' });
    
    const person = people.find(p => p.id === personId);
    const companyId = person?.company_id;
    setCurrentCompanyId(companyId || null);
    
    const company = companies.find(c => c.id === companyId);
    
    addLog(`Starting research for ${personName}`);
    addLog(`Target company: ${company?.name || 'Unknown'} (ID: ${companyId})`);
    addLog(`Mode: Real web search analysis`);

    try {
      const response = await fetch(`${API_BASE}/enrich/${personId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }
      
      const job = await response.json();
      
      if (job.company_id) {
        setCurrentCompanyId(job.company_id);
        addLog(`Research will save to company ID: ${job.company_id}`);
      }
      
      addLog(`Research job ${job.job_id} queued successfully`);
      addLog(`Estimated duration: ${job.estimated_duration || '5-10 minutes'}`);
      addLog(`Watch for real-time progress updates below...`);
      
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      setError(`Failed to start research: ${errorMsg}`);
      setIsLoading(false);
      addLog(`Failed to initialize research job: ${errorMsg}`);
    }
  };

  const formatFieldName = (field: string): string => {
    return field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  const getConnectionStatusColor = (): string => {
    switch (connectionStatus) {
      case 'connected': return 'bg-green-500';
      case 'connecting': return 'bg-yellow-500';
      case 'disconnected': return 'bg-red-500';
      default: return 'bg-gray-500';
    }
  };

  const getResearchModeColor = (snippet: ContextSnippet): string => {
    return snippet.snippet_type === 'real_search_research' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600';
  };

  const getResearchModeLabel = (snippet: ContextSnippet): string => {
    return snippet.snippet_type === 'real_search_research' ? 'REAL WEB RESEARCH' : 'BASIC RESEARCH';
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto px-6 py-8">
        <div className="text-center mb-8 pb-6 border-b border-gray-200">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Alpha Deep Research Agent
          </h1>
          <p className="text-gray-600 mb-4">
            Company intelligence using live web data
          </p>
          
          <div className="flex items-center justify-center gap-4 text-sm">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${getConnectionStatusColor()}`}></div>
              <span className="text-gray-600">WebSocket: {connectionStatus}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-gray-600">Real Search Analysis</span>
            </div>
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <div className="text-red-800">
              <strong>Error:</strong> {error}
            </div>
            <button 
              onClick={() => setError(null)}
              className="mt-2 text-red-600 hover:text-red-800 text-sm underline"
            >
              Dismiss
            </button>
          </div>
        )}

        <section className="bg-white border border-gray-200 rounded-lg p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Research Targets</h2>
          {people.length === 0 ? (
            <div className="text-gray-500">Loading research targets...</div>
          ) : (
            <div className="space-y-4">
              {people.map((person) => (
                <div key={person.id} className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                  <div className="flex justify-between items-center">
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900 mb-2">
                        {person.full_name}
                      </h3>
                      <div className="space-y-1 text-sm text-gray-600">
                        <p><span className="font-medium">Title:</span> {person.title}</p>
                        <p><span className="font-medium">Email:</span> {person.email}</p>
                        <p><span className="font-medium">Company:</span> {companies.find(c => c.id === person.company_id)?.name || 'Unknown'}</p>
                      </div>
                    </div>
                    <div className="flex gap-3">
                      <button
                        className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white px-4 py-2 rounded-lg font-medium transition-colors"
                        onClick={() => runResearch(person.id, person.full_name)}
                        disabled={isLoading}
                      >
                        {isLoading ? 'Research Running...' : 'Start Research'}
                      </button>
                      <button
                        className="bg-gray-600 hover:bg-gray-700 disabled:bg-gray-400 text-white px-4 py-2 rounded-lg font-medium transition-colors"
                        onClick={() => fetchResults(person.company_id)}
                        disabled={isLoading}
                      >
                        Load Results
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
          
          <div className="mt-6 pt-4 border-t border-gray-200">
            <h4 className="text-sm font-semibold text-gray-700 mb-3">Debug Tools</h4>
            <div className="flex gap-3">
              <button
                className="bg-gray-600 hover:bg-gray-700 disabled:bg-gray-400 text-white px-3 py-1 rounded text-sm"
                onClick={debugDatabase}
                disabled={isLoading}
              >
                Debug Database
              </button>
              <button
                className="bg-gray-600 hover:bg-gray-700 disabled:bg-gray-400 text-white px-3 py-1 rounded text-sm"
                onClick={checkSystemHealth}
                disabled={isLoading}
              >
                Check Health
              </button>
              <button
                className="bg-gray-600 hover:bg-gray-700 disabled:bg-gray-400 text-white px-3 py-1 rounded text-sm"
                onClick={() => {
                  setError(null);
                  setLogs([]);
                  addLog('Console cleared');
                }}
                disabled={isLoading}
              >
                Clear Console
              </button>
            </div>
          </div>
        </section>

        {progress && (
          <section className="bg-white border border-gray-200 rounded-lg p-6 mb-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Research Progress</h2>
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
              <div className="flex justify-between items-center mb-3">
                <span className="px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800">
                  {progress.research_mode || 'PROCESSING'}
                </span>
                <div className="text-lg font-semibold text-gray-900">
                  {progress.percent}% Complete
                </div>
              </div>
              
              <div className="w-full bg-gray-200 rounded-full h-2 mb-3">
                <div 
                  className="bg-blue-600 h-2 rounded-full transition-all duration-500 ease-out"
                  style={{ width: `${progress.percent}%` }}
                />
              </div>
              
              <div className="mb-2">
                <span className="font-medium text-gray-900">Status:</span>
                <span className="ml-2 text-gray-700">{progress.msg}</span>
              </div>
              
              {progress.query && (
                <div className="mt-3 p-3 bg-blue-50 rounded-lg">
                  <span className="font-medium text-blue-900">Current Query:</span>
                  <div className="text-blue-800 text-sm mt-1">{progress.query}</div>
                </div>
              )}
            </div>
          </section>
        )}

        {logs.length > 0 && (
          <section className="bg-white border border-gray-200 rounded-lg p-6 mb-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Research Console</h2>
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 max-h-80 overflow-y-auto font-mono text-sm">
              {logs.map((log, index) => (
                <div key={index} className="text-gray-700 leading-relaxed mb-1">
                  {log}
                </div>
              ))}
            </div>
          </section>
        )}

        {results.length > 0 ? (
          <section className="bg-white border border-gray-200 rounded-lg p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Research Results</h2>
            
            {results.map((snippet) => (
              <div key={snippet.id} className="border border-gray-200 rounded-lg p-6 mb-6">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="text-lg font-semibold text-gray-900">Company Intelligence Report</h3>
                  <span className={`px-3 py-1 rounded-full text-xs font-medium ${getResearchModeColor(snippet)}`}>
                    {getResearchModeLabel(snippet)}
                  </span>
                </div>
                
                {snippet.payload && Object.keys(snippet.payload).length > 0 ? (
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {Object.entries(snippet.payload).map(([key, value]) => (
                      <div key={key} className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                        <h4 className="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-2">
                          {formatFieldName(key)}
                        </h4>
                        <div className="text-gray-700 leading-relaxed text-sm">
                          {value || 'Information not available'}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                    <div className="text-red-800">
                      <strong>No research insights available.</strong> Context snippet may be processing.
                    </div>
                  </div>
                )}
                
                {snippet.source_urls && snippet.source_urls.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-gray-200">
                    <h4 className="text-sm font-semibold text-gray-700 mb-3">
                      Web Sources ({snippet.source_urls.length}):
                    </h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {snippet.source_urls.map((url, index) => (
                        <a 
                          key={index}
                          href={url} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="block text-blue-600 hover:text-blue-800 text-sm hover:underline p-2 bg-blue-50 rounded"
                        >
                          {url.length > 60 ? url.substring(0, 60) + '...' : url}
                        </a>
                      ))}
                    </div>
                  </div>
                )}
                
                <div className="mt-4 p-3 bg-gray-100 rounded-lg text-xs text-gray-600">
                  <span className="font-medium">Snippet ID:</span> {snippet.id} | 
                  <span className="font-medium"> Type:</span> {snippet.snippet_type} |
                  <span className="font-medium"> Created:</span> {new Date(snippet.created_at).toLocaleString()}
                </div>
              </div>
            ))}
          </section>
        ) : (
          <section className="bg-white border border-gray-200 rounded-lg p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">No Research Results</h2>
            <p className="text-gray-600 mb-4">No context snippets found. Follow these steps:</p>
            <ol className="list-decimal list-inside space-y-2 text-gray-600">
              <li>Click "Debug Database" to check system status</li>
              <li>Click "Start Research" to generate new data</li>
              <li>Wait for research to complete (watch the console)</li>
              <li>Results will automatically load when research finishes</li>
            </ol>
          </section>
        )}
      </div>
    </div>
  );
}