import { useState, useRef, useEffect } from 'react';

interface Message {
  id: string;
  role: 'user' | 'mayor';
  content: string;
  timestamp: Date;
  isQuestion?: boolean;
}

interface ConvoyStep {
  id: string;
  rig: string;
  polecat_type: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  description?: string;
}

interface Campaign {
  id: string;
  name: string;
  goal: string;
  status: string;
}

export function MayorPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'mayor',
      content: "Hello! I'm the GTM Mayor. I help plan and execute your go-to-market campaigns. What would you like to accomplish?",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [activeCampaign, setActiveCampaign] = useState<Campaign | null>(null);
  const [convoySteps, setConvoySteps] = useState<ConvoyStep[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await fetch('/api/v1/mayor/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: input,
          campaign_id: activeCampaign?.id,
          conversation_history: messages.map((m) => ({
            role: m.role,
            content: m.content,
          })),
        }),
      });

      const data = await response.json();

      const mayorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'mayor',
        content: data.data.response,
        timestamp: new Date(),
        isQuestion: data.data.is_question,
      };

      setMessages((prev) => [...prev, mayorMessage]);

      // Update campaign and convoy if returned
      if (data.data.campaign) {
        setActiveCampaign(data.data.campaign);
      }
      if (data.data.convoy_steps) {
        setConvoySteps(data.data.convoy_steps);
      }
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'mayor',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const getStepIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return '✓';
      case 'running':
        return '●';
      case 'failed':
        return '✗';
      default:
        return '○';
    }
  };

  const getStepColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'text-green-600 bg-green-50 border-green-200';
      case 'running':
        return 'text-blue-600 bg-blue-50 border-blue-200 animate-pulse';
      case 'failed':
        return 'text-red-600 bg-red-50 border-red-200';
      default:
        return 'text-gray-400 bg-gray-50 border-gray-200';
    }
  };

  const getRigDisplayName = (rig: string) => {
    const names: Record<string, string> = {
      content_factory: 'Content Factory',
      sdr_hive: 'SDR Hive',
      social_command: 'Social Command',
      press_room: 'Press Room',
      intelligence_station: 'Intelligence Station',
      landing_pad: 'Landing Pad',
      wire: 'The Wire',
      repo_watch: 'Repo Watch',
    };
    return names[rig] || rig;
  };

  const getPolecatDisplayName = (polecat: string) => {
    return polecat
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  return (
    <div className="h-[calc(100vh-4rem)] flex">
      {/* Left Panel - Chat with Mayor */}
      <div className="flex-1 flex flex-col border-r border-gray-200">
        {/* Header */}
        <div className="p-4 border-b border-gray-200 bg-gradient-to-r from-indigo-600 to-purple-600">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center">
              <span className="text-xl">🎖️</span>
            </div>
            <div>
              <h1 className="text-lg font-semibold text-white">GTM Mayor</h1>
              <p className="text-sm text-indigo-100">Campaign Orchestrator</p>
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                  message.role === 'user'
                    ? 'bg-indigo-600 text-white rounded-br-md'
                    : 'bg-white text-gray-800 shadow-sm border border-gray-100 rounded-bl-md'
                }`}
              >
                {message.role === 'mayor' && message.isQuestion && (
                  <span className="inline-block px-2 py-0.5 text-xs bg-amber-100 text-amber-700 rounded-full mb-2">
                    Question
                  </span>
                )}
                <p className="whitespace-pre-wrap">{message.content}</p>
                <p
                  className={`text-xs mt-1 ${
                    message.role === 'user' ? 'text-indigo-200' : 'text-gray-400'
                  }`}
                >
                  {message.timestamp.toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </p>
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-white rounded-2xl rounded-bl-md px-4 py-3 shadow-sm border border-gray-100">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                  <span
                    className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                    style={{ animationDelay: '0.1s' }}
                  />
                  <span
                    className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                    style={{ animationDelay: '0.2s' }}
                  />
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="p-4 border-t border-gray-200 bg-white">
          <div className="flex gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Tell the Mayor what you want to achieve..."
              className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-3 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              rows={2}
            />
            <button
              onClick={sendMessage}
              disabled={!input.trim() || isLoading}
              className="px-6 py-3 bg-indigo-600 text-white rounded-xl font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Send
            </button>
          </div>
        </div>
      </div>

      {/* Right Panel - Campaign Progress */}
      <div className="w-96 flex flex-col bg-white">
        {/* Campaign Header */}
        <div className="p-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Campaign Progress</h2>
          {activeCampaign ? (
            <div className="mt-2">
              <p className="font-medium text-gray-800">{activeCampaign.name}</p>
              <p className="text-sm text-gray-500">{activeCampaign.goal}</p>
              <span
                className={`inline-block mt-2 px-2 py-0.5 text-xs rounded-full ${
                  activeCampaign.status === 'active'
                    ? 'bg-green-100 text-green-700'
                    : 'bg-gray-100 text-gray-600'
                }`}
              >
                {activeCampaign.status}
              </span>
            </div>
          ) : (
            <p className="mt-2 text-sm text-gray-500">
              No active campaign. Chat with the Mayor to create one.
            </p>
          )}
        </div>

        {/* Progress Stats */}
        {convoySteps.length > 0 && (
          <div className="p-4 border-b border-gray-200 bg-gray-50">
            <div className="grid grid-cols-4 gap-2 text-center">
              <div>
                <p className="text-2xl font-bold text-gray-900">{convoySteps.length}</p>
                <p className="text-xs text-gray-500">Total</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-green-600">
                  {convoySteps.filter((s) => s.status === 'completed').length}
                </p>
                <p className="text-xs text-gray-500">Done</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-blue-600">
                  {convoySteps.filter((s) => s.status === 'running').length}
                </p>
                <p className="text-xs text-gray-500">Running</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-400">
                  {convoySteps.filter((s) => s.status === 'pending').length}
                </p>
                <p className="text-xs text-gray-500">Pending</p>
              </div>
            </div>
          </div>
        )}

        {/* Steps List */}
        <div className="flex-1 overflow-y-auto p-4">
          {convoySteps.length > 0 ? (
            <div className="space-y-3">
              {convoySteps.map((step, index) => (
                <div
                  key={step.id}
                  className={`p-3 rounded-lg border ${getStepColor(step.status)}`}
                >
                  <div className="flex items-start gap-3">
                    <span className="text-lg">{getStepIcon(step.status)}</span>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm">
                        {index + 1}. {getPolecatDisplayName(step.polecat_type)}
                      </p>
                      <p className="text-xs opacity-75">{getRigDisplayName(step.rig)}</p>
                      {step.description && (
                        <p className="text-xs mt-1 opacity-60">{step.description}</p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-gray-100 flex items-center justify-center">
                <span className="text-2xl">📋</span>
              </div>
              <p className="text-gray-500">No tasks yet</p>
              <p className="text-sm text-gray-400 mt-1">
                The Mayor will create tasks when you start a campaign
              </p>
            </div>
          )}
        </div>

        {/* Actions */}
        {convoySteps.length > 0 && activeCampaign?.status === 'draft' && (
          <div className="p-4 border-t border-gray-200">
            <button
              className="w-full py-2 px-4 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors disabled:opacity-50"
              disabled={isLoading}
              onClick={async () => {
                // Start convoy via chat message
                setInput('Start the campaign');
                const userMessage: Message = {
                  id: Date.now().toString(),
                  role: 'user',
                  content: 'Start the campaign',
                  timestamp: new Date(),
                };
                setMessages((prev) => [...prev, userMessage]);
                setIsLoading(true);

                try {
                  const response = await fetch('/api/v1/mayor/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                      message: 'Start the campaign',
                      campaign_id: activeCampaign?.id,
                      conversation_history: messages.map((m) => ({
                        role: m.role,
                        content: m.content,
                      })),
                    }),
                  });

                  const data = await response.json();

                  const mayorMessage: Message = {
                    id: (Date.now() + 1).toString(),
                    role: 'mayor',
                    content: data.data.response,
                    timestamp: new Date(),
                  };
                  setMessages((prev) => [...prev, mayorMessage]);

                  if (data.data.campaign) {
                    setActiveCampaign(data.data.campaign);
                  }
                  if (data.data.convoy_steps) {
                    setConvoySteps(data.data.convoy_steps);
                  }
                } catch (error) {
                  const errorMessage: Message = {
                    id: (Date.now() + 1).toString(),
                    role: 'mayor',
                    content: 'Sorry, I encountered an error starting the campaign.',
                    timestamp: new Date(),
                  };
                  setMessages((prev) => [...prev, errorMessage]);
                } finally {
                  setIsLoading(false);
                  setInput('');
                }
              }}
            >
              {isLoading ? 'Starting...' : 'Start Execution'}
            </button>
          </div>
        )}
        {convoySteps.length > 0 && activeCampaign?.status === 'executing' && (
          <div className="p-4 border-t border-gray-200">
            <div className="flex items-center justify-center gap-2 text-green-600">
              <span className="animate-pulse">●</span>
              <span className="font-medium">Campaign Running</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default MayorPage;
