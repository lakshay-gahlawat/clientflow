// Tiny classname joiner — avoids pulling in `clsx` for something this small.
export function cn(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}
