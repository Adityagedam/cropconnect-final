import { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, Leaf, Lock } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import { API } from "../lib/api";

export default function ResetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const email = useMemo(() => searchParams.get("email") || "", [searchParams]);
  const token = useMemo(() => searchParams.get("token") || "", [searchParams]);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [complete, setComplete] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!email || !token) {
      toast.error("Reset link is missing required data.");
      return;
    }
    if (password.length < 8) {
      toast.error("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirmPassword) {
      toast.error("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API}/auth/password-reset-confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, token, password }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || `Password reset failed with ${response.status}`);
      setComplete(true);
      toast.success("Password reset complete.");
    } catch (error) {
      toast.error(error.message || "Could not reset password.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#FDFBF7] flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Link to="/" className="inline-flex items-center gap-2 group">
            <span className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-[#1B4332] text-[#FDFBF7]">
              <Leaf className="w-5 h-5" strokeWidth={2.5} />
            </span>
            <span className="font-display text-2xl text-[#1A201C] tracking-tight">
              Crop<span className="text-[#1B4332]">Connect</span>
            </span>
          </Link>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-[#D5D1C5]/50 p-8">
          {complete ? (
            <div className="text-center">
              <span className="mx-auto mb-5 inline-flex h-14 w-14 items-center justify-center rounded-full bg-[#E7F3EC] text-[#1B4332]">
                <CheckCircle2 className="h-7 w-7" strokeWidth={2.3} />
              </span>
              <h1 className="font-display text-2xl text-[#1A201C] mb-2">Password Reset</h1>
              <p className="text-sm text-[#1A201C]/60 leading-6">
                Your password has been updated. You can now sign in with the new password.
              </p>
              <Button onClick={() => navigate("/login")} className="mt-7 w-full bg-[#1B4332] hover:bg-[#0F2A1F] text-[#FDFBF7] rounded-full py-5">
                Back to Sign In
              </Button>
            </div>
          ) : (
            <>
              <div className="text-center mb-6">
                <h1 className="font-display text-2xl text-[#1A201C] mb-2">Set New Password</h1>
                <p className="text-sm text-[#1A201C]/60 leading-6">
                  Enter a new password for your CropConnect account.
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-5">
                <div className="space-y-2">
                  <Label htmlFor="password" className="text-[#1A201C]">New Password</Label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#1A201C]/40" />
                    <Input
                      id="password"
                      type="password"
                      placeholder="At least 8 characters"
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      required
                      className="pl-10 bg-[#FDFBF7] border-[#D5D1C5] focus:border-[#1B4332] focus:ring-[#1B4332]/20"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="confirmPassword" className="text-[#1A201C]">Confirm Password</Label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#1A201C]/40" />
                    <Input
                      id="confirmPassword"
                      type="password"
                      placeholder="Re-enter your password"
                      value={confirmPassword}
                      onChange={(event) => setConfirmPassword(event.target.value)}
                      required
                      className="pl-10 bg-[#FDFBF7] border-[#D5D1C5] focus:border-[#1B4332] focus:ring-[#1B4332]/20"
                    />
                  </div>
                </div>

                <Button
                  type="submit"
                  disabled={loading || !email || !token}
                  className="w-full bg-[#1B4332] hover:bg-[#0F2A1F] text-[#FDFBF7] rounded-full py-5"
                >
                  {loading ? "Resetting password..." : "Reset Password"}
                </Button>
              </form>

              <div className="mt-6 text-center">
                <Link to="/login" className="inline-flex items-center gap-2 text-sm text-[#1B4332] font-medium hover:underline">
                  <ArrowLeft className="w-4 h-4" />
                  Back to sign in
                </Link>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
