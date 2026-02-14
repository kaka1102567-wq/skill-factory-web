import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { BuildWizard } from "@/components/build/build-wizard";

export default function NewBuildPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="w-4 h-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-foreground">New Build</h1>
          <p className="text-sm text-muted-foreground">
            Create a new AI skill from your data
          </p>
        </div>
      </div>
      <BuildWizard />
    </div>
  );
}
