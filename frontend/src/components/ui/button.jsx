import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva } from "class-variance-authority";

import { cn } from "@/lib/utils"

// Variant and size styles for buttons
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 active:scale-[0.97]",
  {
    variants: {
      variant: {
        default:
          "bg-text text-background shadow-elevation-1 hover:shadow-elevation-2 hover:-translate-y-[1px]",
        destructive:
          "bg-destructive text-white shadow-elevation-1 hover:shadow-elevation-2 hover:-translate-y-[1px]",
        outline:
          "border border-hairline bg-surface hover:bg-surface-2 text-text shadow-sm",
        secondary:
          "bg-surface-2 text-text border border-hairline hover:bg-surface-2/80 shadow-sm",
        ghost: "hover:bg-surface-2 text-text",
        link: "text-accent underline-offset-4 hover:underline",
      },
      size: {
        default: "min-h-[44px] sm:h-9 px-4 py-2",
        sm: "min-h-[44px] sm:h-8 rounded-xl px-3 text-xs py-2 sm:py-1",
        lg: "h-10 rounded-xl px-8",
        icon: "min-h-[44px] min-w-[44px] sm:h-9 sm:w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

// Styled button with Radix slot support
function Button({ className = '', variant = 'default', size = 'default', asChild = false, ...props }) {
  const Comp = asChild ? Slot : "button"
  return (
    <Comp
      className={cn(buttonVariants({ variant, size, className }))}
      {...props} />
  );
}
Button.displayName = "Button"

export { Button, buttonVariants }
