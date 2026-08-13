import { ReactNode } from "react";
import { X } from "lucide-react";

export function Modal({
  open, onClose, title, children, maxWidth = "max-w-md",
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  maxWidth?: string;
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className={`relative w-full ${maxWidth} card p-6 max-h-[90vh] overflow-y-auto`}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display text-xl text-gold-light">{title}</h2>
          <button onClick={onClose} className="text-neutral-500 hover:text-neutral-200 transition">
            <X size={18} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
