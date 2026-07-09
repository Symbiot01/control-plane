import React, { useRef, useEffect, useState } from 'react';

interface WheelPickerProps {
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  label?: string;
}

const ITEM_WIDTH = 90; // enough space for '14 Days'

export default function WheelPicker({ value, onChange, min, max, label }: WheelPickerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const items = Array.from({ length: max - min + 1 }, (_, i) => min + i);
  const [isScrolling, setIsScrolling] = useState(false);

  // Sync initial scroll position based on value
  useEffect(() => {
    if (containerRef.current && !isScrolling) {
      const index = items.indexOf(value);
      if (index !== -1) {
        containerRef.current.scrollLeft = index * ITEM_WIDTH;
      }
    }
  }, [value, items, isScrolling]);

  const handleScroll = () => {
    if (!containerRef.current) return;
    
    setIsScrolling(true);
    
    // Clear the timeout if it exists
    if ((containerRef.current as any).scrollTimeout) {
      clearTimeout((containerRef.current as any).scrollTimeout);
    }
    
    // Set a timeout to detect when scrolling ends
    (containerRef.current as any).scrollTimeout = setTimeout(() => {
      setIsScrolling(false);
      const scrollLeft = containerRef.current!.scrollLeft;
      const index = Math.round(scrollLeft / ITEM_WIDTH);
      
      if (index >= 0 && index < items.length) {
        const newValue = items[index];
        if (newValue !== value) {
          onChange(newValue);
        }
        // snap precisely
        containerRef.current!.scrollTo({
          left: index * ITEM_WIDTH,
          behavior: 'smooth'
        });
      }
    }, 150);
  };

  return (
    <div className="flex flex-col border-2 border-border bg-background !shadow-[4px_4px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] p-4 w-full relative">
      {label && <div className="font-mono text-xs font-bold uppercase mb-2 text-muted-foreground w-full">{label}</div>}
      
      <div 
        className="relative w-full h-[50px] overflow-hidden" 
        style={{ maskImage: 'linear-gradient(to right, transparent, black 25%, black 75%, transparent)', WebkitMaskImage: 'linear-gradient(to right, transparent, black 25%, black 75%, transparent)' }}
      >
        {/* Highlight Box */}
        <div 
          className="absolute top-0 left-1/2 h-full -translate-x-1/2 border-x-2 border-slate-900 dark:border-white pointer-events-none bg-muted/20"
          style={{ width: `${ITEM_WIDTH}px` }}
        />

        {/* Scrollable Container */}
        <div 
          ref={containerRef}
          onScroll={handleScroll}
          className="h-full w-full overflow-x-auto snap-x snap-mandatory flex items-center scrollbar-hide select-none"
          style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
        >
          {/* Left Padding for first item to be centerable */}
          <div className="shrink-0 pointer-events-none" style={{ width: `calc(50% - ${ITEM_WIDTH / 2}px)` }} />
          
          {items.map(item => (
            <div 
              key={item} 
              className="flex-shrink-0 flex items-center justify-center snap-center h-full font-display-lg text-lg font-bold cursor-pointer transition-colors"
              style={{ width: `${ITEM_WIDTH}px`, color: item === value ? 'inherit' : 'var(--muted-foreground)' }}
              onClick={() => {
                const idx = items.indexOf(item);
                containerRef.current?.scrollTo({ left: idx * ITEM_WIDTH, behavior: 'smooth' });
                onChange(item);
              }}
            >
              {item} {item === 1 ? 'Day' : 'Days'}
            </div>
          ))}
          
          {/* Right Padding for last item to be centerable */}
          <div className="shrink-0 pointer-events-none" style={{ width: `calc(50% - ${ITEM_WIDTH / 2}px)` }} />
        </div>
      </div>
    </div>
  );
}
