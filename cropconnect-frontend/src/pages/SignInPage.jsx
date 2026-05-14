import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import axios from "axios";
import { Leaf, Mail, Lock, User, Phone, ArrowRight, Eye, EyeOff, MapPin } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import { API, storeAuthToken, storeCsrfToken, storeSessionUser } from "../lib/api";
import { INDIA_STATES, getDistrictOptions, getPlaceOptions } from "../lib/indiaLocations";

const locationSelectClass =
  "h-10 w-full rounded-md border border-[#D5D1C5] bg-[#FDFBF7] pl-10 pr-8 text-base text-[#1A201C] shadow-sm focus:border-[#1B4332] focus:outline-none focus:ring-2 focus:ring-[#1B4332]/20 disabled:cursor-not-allowed disabled:opacity-50 md:text-sm";

export default function SignInPage() {
  const navigate = useNavigate();
  const [showPassword, setShowPassword] = useState(false);
  const [formData, setFormData] = useState({
    fullName: "",
    email: "",
    phone: "",
    password: "",
    confirmPassword: "",
    state: "",
    district: "",
    locationType: "city", // "city" or "village"
    city: "",
    village: "",
    landSize: "",
  });
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(1);
  const districtOptions = useMemo(() => getDistrictOptions(formData.state), [formData.state]);
  const placeOptions = useMemo(
    () => getPlaceOptions(formData.state, formData.district),
    [formData.state, formData.district]
  );
  const locationFieldName = formData.locationType === "city" ? "city" : "village";

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => {
      const next = {
        ...prev,
        [name]: value,
      };

      if (name === "state") {
        next.district = "";
        next.city = "";
        next.village = "";
      }
      if (name === "district" || name === "locationType") {
        next.city = "";
        next.village = "";
      }

      return next;
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (step === 1) {
      // Move to step 2
      setStep(2);
      return;
    }

    if (formData.password !== formData.confirmPassword) {
      toast.error("Passwords do not match");
      return;
    }

    if (formData.password.length < 8) {
      toast.error("Password must be at least 8 characters");
      return;
    }

    if (!formData.state || !formData.district || (formData.locationType === "city" && !formData.city) || (formData.locationType === "village" && !formData.village)) {
      toast.error("Please select your location");
      setStep(1);
      return;
    }

    setLoading(true);

    try {
      const location = formData.locationType === "city" ? formData.city : formData.village;
      const response = await axios.post(
        `${API}/auth/signup`,
        {
          name: formData.fullName,
          email: formData.email,
          password: formData.password,
          phone: formData.phone,
          state: formData.state,
          district: formData.district,
          location,
          land_size: formData.landSize ? Number(formData.landSize) : null,
          location_type: formData.locationType,
          city: formData.locationType === "city" ? formData.city : "",
          village: formData.locationType === "village" ? formData.village : "",
          sensors: "0",
          pumps: "0",
          sensor_setup_complete: false,
          sensor_setup_status: "pending",
        },
        { withCredentials: true }
      );
      storeAuthToken(response.data.token);
      storeCsrfToken(response.data.csrfToken);
      storeSessionUser(response.data.user);

      toast.success("Account created successfully! Welcome to CropConnect.");
      navigate("/dashboard");
    } catch (err) {
      const detail = err?.response?.data?.detail;
      if (!err?.response) {
        toast.error(`Could not connect to backend at ${API}. Please try again.`);
      } else {
        toast.error(typeof detail === "string" ? detail : "Could not create account");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#FDFBF7] flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <Link
            to="/"
            className="inline-flex items-center gap-2 group"
          >
            <span className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-[#1B4332] text-[#FDFBF7]">
              <Leaf className="w-5 h-5" strokeWidth={2.5} />
            </span>
            <span className="font-display text-2xl text-[#1A201C] tracking-tight">
              Crop<span className="text-[#1B4332]">Connect</span>
            </span>
          </Link>
        </div>

        {/* Form Card */}
        <div className="bg-white rounded-2xl shadow-sm border border-[#D5D1C5]/50 p-8">
          <div className="text-center mb-6">
            <h1 className="font-display text-2xl text-[#1A201C] mb-2">
              Create Account
            </h1>
            <p className="text-sm text-[#1A201C]/60">
              Join CropConnect and transform your farming experience
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="fullName" className="text-[#1A201C]">
                Full Name
              </Label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#1A201C]/40" />
                <Input
                  id="fullName"
                  name="fullName"
                  type="text"
                  placeholder="--"
                  value={formData.fullName}
                  onChange={handleChange}
                  required
                  className="pl-10 bg-[#FDFBF7] border-[#D5D1C5] focus:border-[#1B4332] focus:ring-[#1B4332]/20"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="email" className="text-[#1A201C]">
                Email Address
              </Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#1A201C]/40" />
                <Input
                  id="email"
                  name="email"
                  type="email"
                  placeholder="--"
                  value={formData.email}
                  onChange={handleChange}
                  required
                  className="pl-10 bg-[#FDFBF7] border-[#D5D1C5] focus:border-[#1B4332] focus:ring-[#1B4332]/20"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="phone" className="text-[#1A201C]">
                Phone Number
              </Label>
              <div className="relative">
                <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#1A201C]/40" />
                <Input
                  id="phone"
                  name="phone"
                  type="tel"
                  placeholder="--"
                  value={formData.phone}
                  onChange={handleChange}
                  required
                  className="pl-10 bg-[#FDFBF7] border-[#D5D1C5] focus:border-[#1B4332] focus:ring-[#1B4332]/20"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" className="text-[#1A201C]">
                Password
              </Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#1A201C]/40" />
                <Input
                  id="password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="At least 8 characters"
                  value={formData.password}
                  onChange={handleChange}
                  required
                  className="pl-10 pr-10 bg-[#FDFBF7] border-[#D5D1C5] focus:border-[#1B4332] focus:ring-[#1B4332]/20"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#1A201C]/40 hover:text-[#1A201C]/70"
                >
                  {showPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="confirmPassword" className="text-[#1A201C]">
                Confirm Password
              </Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#1A201C]/40" />
                <Input
                  id="confirmPassword"
                  name="confirmPassword"
                  type={showPassword ? "text" : "password"}
                  placeholder="Re-enter your password"
                  value={formData.confirmPassword}
                  onChange={handleChange}
                  required
                  className="pl-10 bg-[#FDFBF7] border-[#D5D1C5] focus:border-[#1B4332] focus:ring-[#1B4332]/20"
                />
              </div>
            </div>

            {step >= 2 && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="state" className="text-[#1A201C]">
                    State
                  </Label>
                  <div className="relative">
                    <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#1A201C]/40" />
                    <select
                      id="state"
                      name="state"
                      value={formData.state}
                      onChange={handleChange}
                      required
                      className={locationSelectClass}
                    >
                      <option value="">Select state</option>
                      {INDIA_STATES.map((state) => (
                        <option key={state.code} value={state.name}>
                          {state.name}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label className="text-[#1A201C]">
                    Location Type
                  </Label>
                  <div className="flex gap-4">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name="locationType"
                        value="city"
                        checked={formData.locationType === "city"}
                        onChange={handleChange}
                        className="text-[#1B4332] focus:ring-[#1B4332]/20"
                      />
                      <span className="text-[#1A201C]">City</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name="locationType"
                        value="village"
                        checked={formData.locationType === "village"}
                        onChange={handleChange}
                        className="text-[#1B4332] focus:ring-[#1B4332]/20"
                      />
                      <span className="text-[#1A201C]">Village</span>
                    </label>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="district" className="text-[#1A201C]">
                    District
                  </Label>
                  <div className="relative">
                    <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#1A201C]/40" />
                    <select
                      id="district"
                      name="district"
                      value={formData.district}
                      onChange={handleChange}
                      required
                      disabled={!formData.state}
                      className={locationSelectClass}
                    >
                      <option value="">
                        {formData.state ? "Select district" : "Select state first"}
                      </option>
                      {districtOptions.map((district) => (
                        <option key={district} value={district}>
                          {district}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor={locationFieldName} className="text-[#1A201C]">
                    {formData.locationType === "city" ? "City" : "Village"}
                  </Label>
                  <div className="relative">
                    <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#1A201C]/40" />
                    {formData.locationType === "city" ? (
                      <select
                        id="city"
                        name="city"
                        value={formData.city}
                        onChange={handleChange}
                        required
                        disabled={!formData.district}
                        className={locationSelectClass}
                      >
                        <option value="">
                          {formData.district ? "Select city" : "Select district first"}
                        </option>
                        {placeOptions.map((place) => (
                          <option key={place} value={place}>
                            {place}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <select
                        id="village"
                        name="village"
                        value={formData.village}
                        onChange={handleChange}
                        required
                        disabled={!formData.district}
                        className={locationSelectClass}
                      >
                        <option value="">
                          {formData.district ? "Select village / area" : "Select district first"}
                        </option>
                        {placeOptions.map((place) => (
                          <option key={place} value={place}>
                            {place}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="landSize" className="text-[#1A201C]">
                    Land Size (acres)
                  </Label>
                  <div className="relative">
                    <Input
                      id="landSize"
                      name="landSize"
                      type="number"
                      step="0.1"
                      min="0.1"
                      placeholder="--"
                      value={formData.landSize}
                      onChange={handleChange}
                      className="pl-10 bg-[#FDFBF7] border-[#D5D1C5] focus:border-[#1B4332] focus:ring-[#1B4332]/20"
                    />
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[#1A201C]/40 text-sm">
                      acres
                    </span>
                  </div>
                </div>
              </>
            )}

            <Button
              type="submit"
              disabled={loading}
              className="w-full bg-[#1B4332] hover:bg-[#0F2A1F] text-[#FDFBF7] rounded-full py-5"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="w-4 h-4 border-2 border-[#FDFBF7]/30 border-t-[#FDFBF7] rounded-full animate-spin" />
                  Creating account...
                </span>
              ) : step === 1 ? (
                <span className="flex items-center gap-2">
                  Next: Location Details
                  <ArrowRight className="w-4 h-4" />
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  Create Account
                  <ArrowRight className="w-4 h-4" />
                </span>
              )}
            </Button>
          </form>

          <div className="mt-6 text-center">
            <p className="text-sm text-[#1A201C]/60">
              Already have an account?{" "}
              <Link
                to="/login"
                className="text-[#1B4332] font-medium hover:underline"
              >
                Sign in
              </Link>
            </p>
          </div>
        </div>

        {/* Footer text */}
        <p className="text-center text-xs text-[#1A201C]/40 mt-6">
          By creating an account, you agree to CropConnect's{" "}
          <Link to="/terms" className="underline">
            Terms of Service
          </Link>{" "}
          and{" "}
          <Link to="/privacy" className="underline">
            Privacy Policy
          </Link>
          .
        </p>
      </div>
    </div>
  );
}
