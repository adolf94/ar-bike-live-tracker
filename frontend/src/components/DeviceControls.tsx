import { useState, useEffect } from 'react';
import { Shield, Lock, Unlock, X, Check, AlertCircle, Loader2 } from 'lucide-react';

export function DeviceControls() {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [targetCommand, setTargetCommand] = useState<'DY' | 'KY' | null>(null);

  const [pin, setPin] = useState<string>('');
  const [isShaking, setIsShaking] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Auto-dismiss toast
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  // Handle keypad input
  const handleKeyPress = (num: string) => {
    if (pin.length < 4 && !isLoading) {
      setPin(prev => prev + num);
      setErrorMessage(null);
    }
  };

  // Handle backspace
  const handleBackspace = () => {
    if (pin.length > 0 && !isLoading) {
      setPin(prev => prev.slice(0, -1));
      setErrorMessage(null);
    }
  };

  // Handle clear
  const handleClear = () => {
    if (!isLoading) {
      setPin('');
      setErrorMessage(null);
    }
  };

  // Submit PIN when it reaches 4 digits
  useEffect(() => {
    if (pin.length === 4 && targetCommand) {
      submitCommand(pin, targetCommand);
    }
  }, [pin, targetCommand]);

  const submitCommand = async (enteredPin: string, command: 'DY' | 'KY') => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const backendBase = `http://${window.location.hostname}:7071`;
      const res = await fetch(`${backendBase}/api/device/command`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          command,
          pin: enteredPin,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || 'Failed to send command');
      }

      // Success
      setToast({
        message: `Command ${command === 'DY' ? 'Cut Engine' : 'Restore Engine'} sent successfully!`,
        type: 'success',
      });
      closeModal();
    } catch (err: any) {
      console.error(err);
      setErrorMessage(err.message || 'An error occurred');
      setPin(''); // Reset PIN for retry
      setIsShaking(true);
      setTimeout(() => setIsShaking(false), 400); // 400ms match with CSS shake duration
    } finally {
      setIsLoading(false);
    }
  };

  const openModal = (command: 'DY' | 'KY') => {
    setTargetCommand(command);
    setPin('');
    setErrorMessage(null);
    setIsModalOpen(true);
    setIsDropdownOpen(false);
  };

  const closeModal = () => {
    if (!isLoading) {
      setIsModalOpen(false);
      setTargetCommand(null);
      setPin('');
      setErrorMessage(null);
    }
  };

  return (
    <>
      {/* Inline styles for custom animations to bypass tailwind config changes */}
      <style dangerouslySetInnerHTML={{
        __html: `
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          20%, 60% { transform: translateX(-6px); }
          40%, 80% { transform: translateX(6px); }
        }
        .animate-shake {
          animation: shake 0.35s ease-in-out;
        }
      `}} />

      <div className="relative">
        {/* Actions Button */}
        <button
          onClick={() => setIsDropdownOpen(prev => !prev)}
          className={`flex items-center gap-1.5 px-3 py-1.5 md:px-4 md:py-2 rounded-xl text-xs md:text-sm font-semibold border transition-all duration-200 cursor-pointer shadow-sm select-none ${isDropdownOpen
              ? 'bg-primary/20 border-primary text-primary'
              : 'bg-dark-panel hover:bg-dark-border border-dark-border text-slate-300 hover:text-white'
            }`}
        >
          <Shield className="w-4 h-4" />
          <span>Actions</span>
        </button>

        {/* Backdrop for closing dropdown */}
        {isDropdownOpen && (
          <div
            className="fixed inset-0 z-40 bg-transparent"
            onClick={() => setIsDropdownOpen(false)}
          />
        )}

        {/* Dropdown Menu */}
        {isDropdownOpen && (
          <div className="absolute right-0 mt-2 w-48 rounded-xl bg-dark-panel border border-dark-border p-1.5 shadow-2xl z-50 animate-in fade-in slide-in-from-top-2 duration-150">
            <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider px-2.5 py-1.5">
              Device Management
            </div>

            {/* Cut Engine option */}
            <button
              onClick={() => openModal('DY')}
              className="w-full flex items-center gap-2.5 px-2.5 py-2 text-xs md:text-sm font-medium rounded-lg text-slate-300 hover:text-white hover:bg-danger/10 hover:border-danger/10 transition-colors cursor-pointer text-left"
            >
              <div className="p-1 rounded bg-danger/10 text-danger shrink-0">
                <Lock className="w-3.5 h-3.5" />
              </div>
              <span>Cut Engine (DY)</span>
            </button>

            {/* Restore Engine option */}
            <button
              onClick={() => openModal('KY')}
              className="w-full flex items-center gap-2.5 px-2.5 py-2 text-xs md:text-sm font-medium rounded-lg text-slate-300 hover:text-white hover:bg-success/10 hover:border-success/10 transition-colors cursor-pointer text-left"
            >
              <div className="p-1 rounded bg-success/10 text-success shrink-0">
                <Unlock className="w-3.5 h-3.5" />
              </div>
              <span>Restore Engine (KY)</span>
            </button>
          </div>
        )}
      </div>

      {/* Security Verification Passcode Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-dark/70 backdrop-blur-md transition-opacity"
            onClick={closeModal}
          />

          {/* Modal Content */}
          <div className="relative w-full max-w-sm rounded-3xl bg-dark-panel/90 border border-dark-border p-6 shadow-2xl z-10 flex flex-col items-center gap-6 animate-in zoom-in-95 duration-200">

            {/* Header */}
            <div className="w-full flex justify-between items-center">
              <span className="text-xs font-bold text-slate-500 uppercase tracking-widest flex items-center gap-1.5">
                <Shield className="w-3.5 h-3.5 text-primary" />
                Security Access
              </span>
              <button
                onClick={closeModal}
                disabled={isLoading}
                className="p-1.5 rounded-full hover:bg-dark-border text-slate-400 hover:text-white transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Title / Description */}
            <div className="text-center">
              <h3 className="text-lg font-bold text-white">Enter Security PIN</h3>
              <p className="text-xs text-slate-400 mt-1">
                Required to authorize <span className={targetCommand === 'DY' ? 'text-danger font-semibold' : 'text-success font-semibold'}>
                  {targetCommand === 'DY' ? 'Engine Cutoff (DY)' : 'Engine Restoration (KY)'}
                </span>
              </p>
            </div>

            {/* Passcode Circles with Shake Animation */}
            <div className={`flex flex-col items-center gap-2 ${isShaking ? 'animate-shake' : ''}`}>
              <div className="flex gap-4 my-2">
                {[...Array(4)].map((_, i) => (
                  <div
                    key={i}
                    className={`w-3.5 h-3.5 rounded-full border transition-all duration-100 ${i < pin.length
                        ? (targetCommand === 'DY'
                          ? 'bg-danger border-danger scale-110 shadow-[0_0_8px_rgba(239,68,68,0.5)]'
                          : 'bg-success border-success scale-110 shadow-[0_0_8px_rgba(16,185,129,0.5)]')
                        : 'border-slate-500 bg-transparent'
                      }`}
                  />
                ))}
              </div>
              {errorMessage && (
                <div className="text-xs text-danger font-semibold flex items-center gap-1 mt-1 animate-in fade-in duration-200">
                  <AlertCircle className="w-3 h-3" />
                  {errorMessage}
                </div>
              )}
            </div>

            {/* Keypad */}
            <div className="grid grid-cols-3 gap-x-6 gap-y-3.5 w-full max-w-[270px]">
              {['1', '2', '3', '4', '5', '6', '7', '8', '9'].map(num => (
                <button
                  key={num}
                  onClick={() => handleKeyPress(num)}
                  disabled={isLoading}
                  className="w-16 h-16 rounded-full bg-dark hover:bg-dark-border border border-dark-border text-white text-xl font-bold flex items-center justify-center transition-all duration-150 cursor-pointer active:scale-90 select-none disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {num}
                </button>
              ))}

              {/* Reset key */}
              <button
                onClick={handleClear}
                disabled={isLoading || pin.length === 0}
                className="w-16 h-16 rounded-full text-slate-400 hover:text-white text-xs font-semibold flex items-center justify-center transition-colors cursor-pointer active:scale-95 disabled:opacity-30 disabled:cursor-not-allowed select-none"
              >
                Clear
              </button>

              {/* 0 Key */}
              <button
                onClick={() => handleKeyPress('0')}
                disabled={isLoading}
                className="w-16 h-16 rounded-full bg-dark hover:bg-dark-border border border-dark-border text-white text-xl font-bold flex items-center justify-center transition-all duration-150 cursor-pointer active:scale-90 select-none disabled:opacity-50 disabled:cursor-not-allowed"
              >
                0
              </button>

              {/* Backspace Key */}
              <button
                onClick={handleBackspace}
                disabled={isLoading || pin.length === 0}
                className="w-16 h-16 rounded-full text-slate-400 hover:text-white text-xs font-semibold flex items-center justify-center transition-colors cursor-pointer active:scale-95 disabled:opacity-30 disabled:cursor-not-allowed select-none"
              >
                Delete
              </button>
            </div>

            {/* Loader Overlay inside Modal */}
            {isLoading && (
              <div className="absolute inset-0 bg-dark-panel/80 backdrop-blur-sm rounded-3xl flex flex-col items-center justify-center gap-3">
                <Loader2 className="w-8 h-8 text-primary animate-spin" />
                <span className="text-sm font-semibold text-slate-200">Sending Command...</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Success/Error Toast Notification Overlay */}
      {toast && (
        <div className="fixed top-6 right-6 z-50 animate-in slide-in-from-top-5 fade-in duration-300">
          <div className={`p-4 rounded-xl shadow-2xl border flex items-center gap-3 min-w-[300px] ${toast.type === 'success'
              ? 'bg-success/10 border-success/30 text-success'
              : 'bg-danger/10 border-danger/30 text-danger'
            }`}>
            {toast.type === 'success' ? (
              <Check className="w-5 h-5 shrink-0" />
            ) : (
              <AlertCircle className="w-5 h-5 shrink-0" />
            )}
            <div className="flex-1 text-sm font-semibold">{toast.message}</div>
            <button
              onClick={() => setToast(null)}
              className="p-0.5 rounded-full hover:bg-black/10 transition-colors text-inherit"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </>
  );
}
