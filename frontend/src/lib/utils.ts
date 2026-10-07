import { clsx, ClassValue } from "clsx";
import { twMerge } from "tailwind-merge"

// Merges Tailwind classes and resolves conflicts
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
