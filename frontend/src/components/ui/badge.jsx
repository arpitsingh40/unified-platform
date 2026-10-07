import * as React from "react"
import { cva } from "class-variance-authority";

import { cn } from "@/lib/utils"

// Variant styles for badge components
const badgeVariants = cva(
  "inline-flex items-center rounded-lg border px-2.5 py-0.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-text text-background shadow-sm",
        secondary:
          "border-transparent bg-surface-2 text-text",
        destructive:
          "border-transparent bg-destructive text-white shadow-sm",
        outline: "border-hairline text-text bg-surface",
        accent: "border-accent/20 bg-accent-wash text-text",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

// Styled status pill component
function Badge({
  className,
  variant,
  ...props
}) {
  return (<div className={cn(badgeVariants({ variant }), className)} {...props} />);
}

export { Badge, badgeVariants }
