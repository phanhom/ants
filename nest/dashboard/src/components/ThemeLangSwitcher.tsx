import { useTheme } from "./theme-provider";
import { useTranslation } from "react-i18next";
import { Moon, Sun, Globe } from "lucide-react";
import { cn } from "@/lib/utils";

export function ThemeLangSwitcher() {
  const { theme, setTheme } = useTheme();
  const { i18n } = useTranslation();

  const toggleTheme = () => {
    setTheme(theme === "dark" ? "light" : "dark");
  };

  const toggleLang = () => {
    const nextLang = i18n.language.startsWith("zh") ? "en" : "zh";
    i18n.changeLanguage(nextLang);
  };

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={toggleLang}
        className={cn(
          "flex h-8 items-center gap-1.5 rounded-md px-2.5 text-xs font-medium text-muted-foreground",
          "hover:bg-surface-hover hover:text-foreground transition-colors"
        )}
      >
        <Globe className="h-3.5 w-3.5" />
        {i18n.language.startsWith("zh") ? "EN" : "中"}
      </button>
      
      <button
        onClick={toggleTheme}
        className={cn(
          "flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground",
          "hover:bg-surface-hover hover:text-foreground transition-colors"
        )}
      >
        {theme === "dark" ? (
          <Sun className="h-4 w-4" />
        ) : (
          <Moon className="h-4 w-4" />
        )}
      </button>
    </div>
  );
}
