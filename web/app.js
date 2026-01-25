/**
 * Sportrauma 2.0 - Core Application Logic
 */

// --- Element Selectors ---
const authScreen = document.getElementById("auth-screen");
const initialAuthView = document.getElementById("initial-auth-view");
const loginView = document.getElementById("login-view");
const signupView = document.getElementById("signup-view");
const accountChoiceView = document.getElementById("account-choice-view");
const whatsappVerifyView = document.getElementById("whatsapp-verify-view");

const dashboardScreen = document.getElementById("dashboard-screen");
const plannerScreen = document.getElementById("planner-screen");
const settingsScreen = document.getElementById("settings-screen");
const userNav = document.getElementById("user-nav");
const output = document.getElementById("output");
const authOutput = document.getElementById("auth-output");

// Buttons & Inputs
const showLoginBtn = document.getElementById("show-login-btn");
const showSignupBtn = document.getElementById("show-signup-btn");
const backToAuthBtns = document.querySelectorAll(".back-to-auth-btn");

const googleLoginBtn = document.getElementById("google-login-btn");
const emailLoginBtn = document.getElementById("email-login-btn");
const emailSignupBtn = document.getElementById("email-signup-btn");
const loginEmailInput = document.getElementById("login-email");
const loginPasswordInput = document.getElementById("login-password");
const signupEmailInput = document.getElementById("signup-email");
const signupPasswordInput = document.getElementById("signup-password");
const saveProfileBtn = document.getElementById("save-profile");

const choosePersonalBtn = document.getElementById("choose-personal-btn");
const chooseTherapistBtn = document.getElementById("choose-therapist-btn");

// WhatsApp Auth OTP Selectors
const authPhoneWrap = document.getElementById("auth-phone-wrap");
const authOtpWrap = document.getElementById("auth-otp-wrap");
const authPhoneInput = document.getElementById("auth-login-phone");
const authOtpInput = document.getElementById("auth-otp-input");
const authSendOtpBtn = document.getElementById("auth-send-otp-btn");
const authVerifyOtpBtn = document.getElementById("auth-verify-otp-btn");
const authBackToPhoneBtn = document.getElementById("auth-back-to-phone-btn");
const authBackToChoiceBtn = document.getElementById("auth-back-to-choice-btn");

// Nav & Dashboard Selectors
const logoutBtn = document.getElementById("logout-btn");
const navDashboardBtn = document.getElementById("nav-dashboard-btn");
const navPlannerBtn = document.getElementById("nav-planner-btn");
const navSettingsBtn = document.getElementById("nav-settings-btn");
const navSwitchModeBtn = document.getElementById("nav-switch-mode-btn");
const userEmailDisplay = document.getElementById("user-email-display");
const phoneLinkedBadge = document.getElementById("phone-linked-badge");
const connectionStatus = document.getElementById("connection-status");

const sharedAccessCard = document.getElementById("shared-access-card");
const sharedOwnerSelect = document.getElementById("shared-owner-select");
const coachActionsArea = document.getElementById("coach-actions-area");
const coachSendWorkoutBtn = document.getElementById("coach-send-workout-btn");
const therapistAdjustPlanBtn = document.getElementById("therapist-adjust-plan-btn");
const syncDataBtn = document.getElementById("sync-data-btn");
const userSyncDataBtn = document.getElementById("user-sync-data-btn");

const actionsSection = document.getElementById("actions-section");
const profileFormSection = document.getElementById("profile-form-section");
const calendarSection = document.getElementById("calendar-section");
const botConnectCard = document.getElementById("bot-connect-card");
const linkWhatsappCard = document.getElementById("link-whatsapp-card");
const shareManageCard = document.getElementById("share-manage-card");

const advancedSettingsSection = document.getElementById("advanced-settings-section");
const workoutBuilderSection = document.getElementById("workout-builder-section");
const saveSiteSettingsBtn = document.getElementById("save-site-settings-btn");
const workoutListSettings = document.getElementById("workout-list-settings");
const notifMorningInput = document.getElementById("notif-morning");
const notifEveningInput = document.getElementById("notif-evening");

const saveCustomWorkoutBtn = document.getElementById("save-custom-workout-btn");
const customWorkoutsList = document.getElementById("custom-workouts-list");
const wbId = document.getElementById("wb-id");
const wbName = document.getElementById("wb-name");
const wbState = document.getElementById("wb-state");
const wbDuration = document.getElementById("wb-duration");
const wbDesc = document.getElementById("wb-desc");
const wbFull = document.getElementById("wb-full");

const therapistHistoryTable = document.getElementById("therapist-history-table");
const therapistDetailsArea = document.getElementById("therapist-details-area");
const analysisSummary = document.getElementById("analysis-summary");
const analysisPhysical = document.getElementById("analysis-physical");
const analysisSleep = document.getElementById("analysis-sleep");
const analysisSurveys = document.getElementById("analysis-surveys");
const analysisState = document.getElementById("analysis-state");
const analysisNightmares = document.getElementById("analysis-nightmares");
const analysisHrvThreshold = document.getElementById("analysis-hrv-threshold");

const viewOtpSection = document.getElementById("view-otp-section");
const requestViewOtpBtn = document.getElementById("request-view-otp-btn");
const requestViewOtpWrap = document.getElementById("request-view-otp-wrap");
const verifyViewOtpWrap = document.getElementById("verify-view-otp-wrap");
const viewOtpInput = document.getElementById("view-otp-input");
const verifyViewOtpBtn = document.getElementById("verify-view-otp-btn");
const changeViewOwnerBtn = document.getElementById("change-view-owner-btn");

// --- Firebase ---
const firebaseApp = firebase.initializeApp(window.firebaseConfig);
const auth = firebase.auth();
const db = firebase.firestore();
const googleProvider = new firebase.auth.GoogleAuthProvider();

auth.setPersistence(firebase.auth.Auth.Persistence.LOCAL).catch(e => console.error("Auth persistence error:", e));

// --- Global State ---
let metricsChart = null;
let linkedPhone = "";
let viewerMode = localStorage.getItem("preferred_mode") === "therapist";
let sharedOwners = [];
let currentScreen = "dashboard";
let currentRangeDays = 7;

// --- Range Button Handler ---
function initRangeButtons() {
    console.log("Initializing range buttons...");
    const buttons = document.querySelectorAll(".range-btn");
    console.log("Found range buttons:", buttons.length);
    buttons.forEach(btn => {
        btn.addEventListener("click", () => {
            const days = parseInt(btn.getAttribute("data-days"));
            console.log("Range button clicked:", days);
            if (isNaN(days)) return;
            
            currentRangeDays = days;
            
            // Update UI
            document.querySelectorAll(".range-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            
            // Reload data
            const selectedOwner = sharedOwnerSelect ? sharedOwnerSelect.value : null;
            if (viewerMode && selectedOwner) {
                loadSharedInsights(selectedOwner);
            } else {
                loadUserInsights();
            }
        });
    });
}

// --- UI Utilities ---

function setOutput(text, type = "info") {
    if (!output) return;
    output.innerHTML = text || "מוכן לפעולה.";
    output.classList.remove("animate-pulse");
    if (type === "loading") output.classList.add("animate-pulse");
}

function setAuthOutput(text) {
    if (!authOutput) return;
    if (text) {
        authOutput.textContent = text;
        authOutput.classList.remove("hidden");
    } else {
        authOutput.textContent = "";
        authOutput.classList.add("hidden");
    }
}

function showAuthView(viewId) {
    if (authScreen) authScreen.classList.remove("hidden");
    [initialAuthView, loginView, signupView, accountChoiceView, whatsappVerifyView].forEach(v => {
        if (v) v.classList.add("hidden");
    });
    const target = document.getElementById(viewId);
    if (target) target.classList.remove("hidden");
}

function showScreen(screen) {
    console.log("Switching to screen:", screen);
    currentScreen = screen;
    if (!dashboardScreen || !settingsScreen || !plannerScreen) {
        console.warn("Missing screen elements:", { dashboardScreen: !!dashboardScreen, settingsScreen: !!settingsScreen, plannerScreen: !!plannerScreen });
        return;
    }
    if (authScreen) authScreen.classList.add("hidden");
    
    dashboardScreen.classList.add("hidden");
    plannerScreen.classList.add("hidden");
    settingsScreen.classList.add("hidden");

    // Update nav links
    [navDashboardBtn, navPlannerBtn, navSettingsBtn].forEach(btn => {
        if (btn) btn.classList.remove("active");
    });

    if (screen === "settings") {
        if (settingsScreen) settingsScreen.classList.remove("hidden");
        if (navSettingsBtn) navSettingsBtn.classList.add("active");
    } else if (screen === "planner") {
        if (plannerScreen) plannerScreen.classList.remove("hidden");
        if (navPlannerBtn) navPlannerBtn.classList.add("active");
        try {
            initWorkoutMap();
        } catch (e) {
            console.error("Map initialization failed:", e);
            setOutput("שגיאה בטעינת המפה. ודא שחיבור האינטרנט תקין.");
        }
    } else {
        if (dashboardScreen) dashboardScreen.classList.remove("hidden");
        if (navDashboardBtn) navDashboardBtn.classList.add("active");
    }
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

function setViewerUiState(isViewer) {
    viewerMode = isViewer;
    const hideForViewer = [actionsSection, calendarSection, botConnectCard, shareManageCard, linkWhatsappCard, profileFormSection];
    const showForViewer = [sharedAccessCard];
    
    if (isViewer) {
        if (advancedSettingsSection) advancedSettingsSection.classList.remove("hidden");
        if (workoutBuilderSection) workoutBuilderSection.classList.remove("hidden");
    }

    hideForViewer.forEach(el => { if (el) el.classList.toggle("hidden", isViewer); });
    showForViewer.forEach(el => { if (el) el.classList.toggle("hidden", !isViewer); });
    
    if (navSettingsBtn) navSettingsBtn.classList.toggle("hidden", isViewer);
    
    if (isViewer) {
        showScreen("dashboard");
        setOutput("שלום מטפל/ת! בחר/י מטופל/ת כדי להתחיל.");
    } else {
        if (therapistDetailsArea) therapistDetailsArea.classList.add("hidden");
        if (syncDataBtn) syncDataBtn.classList.add("hidden");
    }
}

// --- Data & API Helpers ---

async function callBotAction(action, payload = {}, skipAuth = false) {
    // #region agent log
    fetch('http://127.0.0.1:7243/ingest/ce177355-1ddf-4183-a8e8-17e4e2916611',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'app.js:callBotAction',message:'Calling bot action',data:{action,payload,skipAuth},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'B'})}).catch(()=>{});
    // #endregion
    let headers = { "Content-Type": "application/json" };
    if (!skipAuth) {
        const user = auth.currentUser;
        if (!user) {
            console.error("callBotAction: No user logged in for authenticated action", action);
            throw new Error("נא להתחבר קודם");
        }
        try {
            const token = await user.getIdToken();
            if (!token) {
                console.warn("callBotAction: Empty token returned for action", action);
            }
            headers["Authorization"] = `Bearer ${token}`;
        } catch (tokenErr) {
            console.error("callBotAction: Failed to get ID token", tokenErr);
            throw new Error("שגיאת אימות: לא ניתן להנפיק מפתח גישה.");
        }
    }
    try {
        console.log(`[BotAPI] Calling ${action}...`, skipAuth ? "(Public)" : "(Auth)");
        const res = await fetch(`${window.botApiBase}/site_action`, {
            method: "POST", headers: headers, body: JSON.stringify({ action, payload })
        });
        // #region agent log
        fetch('http://127.0.0.1:7243/ingest/ce177355-1ddf-4183-a8e8-17e4e2916611',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'app.js:callBotAction',message:'Fetch result',data:{status:res.status,ok:res.ok},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'D'})}).catch(()=>{});
        // #endregion
        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            console.error(`[BotAPI] Error ${res.status}:`, errData);
            const errorMap = {
                not_linked: "יש לחבר את הוואטסאפ לבוט תחילה.",
                link_token_expired: "קישור ההרשמה פג תוקף.",
                link_token_used: "הקישור הזה כבר נוצל.",
                invalid_link_token: "הקישור לא תקין."
            };
            throw new Error(errorMap[errData.error] || errData.error || `שגיאת שרת: ${res.status}`);
        }
        return await res.json();
    } catch (e) {
        // #region agent log
        fetch('http://127.0.0.1:7243/ingest/ce177355-1ddf-4183-a8e8-17e4e2916611',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'app.js:callBotAction',message:'Fetch exception',data:{error:e.message},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'D/E'})}).catch(()=>{});
        // #endregion
        console.error("Bot Action Error:", e);
        if (e.name === 'TypeError' && e.message === 'Failed to fetch') {
            throw new Error("שגיאת תקשורת עם השרת (CORS/Network). ודא שהשרת פועל ושכתובת ה-API תקינה.");
        }
        throw e;
    }
}

async function loadUserInsights() {
    try {
        const data = await callBotAction("fetch_insights", { range_days: currentRangeDays });
        const rows = data.rows || [];
        updateStatsGrid(rows);
        renderMetricsChart(rows);
        updateHistoryLists(rows, data.recs || []);
        renderAnalysis(data.analysis, data.deep_report);
    } catch (e) {
        console.error("Insights load error:", e);
        setOutput("שגיאה בטעינת נתונים.");
    }
}

// --- Auth State Handler ---

async function handleAuthStateChange(user) {
    console.log("Auth State Changed:", user ? `User logged in: ${user.email || user.uid}` : "No user");
    
    // Check for share token in URL
    const urlParams = new URLSearchParams(window.location.search);
    const shareToken = urlParams.get("share");
    if (shareToken) {
        console.log("Share token detected:", shareToken);
        localStorage.setItem("pending_share_token", shareToken);
        localStorage.setItem("preferred_mode", "therapist");
        // Clear param from URL
        window.history.replaceState({}, document.title, window.location.pathname);
    }
    
    if (user) {
        authScreen.classList.add("hidden");
        userNav.classList.remove("hidden");
        userEmailDisplay.textContent = user.email;
        userEmailDisplay.classList.remove("hidden");
        setAuthOutput("");

        try {
            console.log("Fetching user status from bot...");
            setOutput("טוען נתוני מערכת...", "loading");
            const who = await callBotAction("whoami");
            linkedPhone = who.phone || "";
            sharedOwners = who.shared_owners || [];
            console.log("Bot status:", who);
            
            const prefMode = localStorage.getItem("preferred_mode");
            console.log("Preferred mode from storage:", prefMode);

            if (!prefMode) {
                console.log("No preferred mode, showing account choice.");
                authScreen.classList.remove("hidden");
                showAuthView("account-choice-view");
                setOutput("שלום! אנא בחר/י סוג חשבון להמשך.");
            } else {
                console.log("Entering dashboard in mode:", prefMode);
                authScreen.classList.add("hidden");
                dashboardScreen.classList.remove("hidden");
                
                if (prefMode === "therapist") {
                    setViewerUiState(true);
                    populateSharedOwners(sharedOwners);
                    if (sharedOwners.length > 0) {
                        const firstOwner = sharedOwners[0];
                        sharedOwnerSelect.value = firstOwner.phone;
                        loadSharedInsights(firstOwner.phone);
                    } else {
                        setOutput("שלום מטפל/ת! עדיין לא שיתפו איתך נתונים.");
                    }
                } else {
                    setViewerUiState(false);
                    phoneLinkedBadge.classList.remove("hidden");
                    
                    // Run these in parallel and don't let one block the others
                    Promise.allSettled([
                        loadUserInsights(),
                        loadShareViewers(),
                        loadAdvancedSettings()
                    ]).then(() => {
                        console.log("Personal dashboard data loaded");
                        try {
                            initWorkoutMap();
                        } catch (mapErr) {
                            console.error("Map initialization failed during startup:", mapErr);
                        }
                    });
                }
            }

            if (linkedPhone && sharedOwners.length > 0) {
                navSwitchModeBtn.classList.remove("hidden");
            } else {
                navSwitchModeBtn.classList.add("hidden");
            }

        } catch (e) {
            console.error("whoami failed or bot action error:", e);
            setOutput("המערכת בטעינה, במידה ולא נטען תוך מספר שניות נסו לרענן.");
            // If it's a new user, they might not be in the bot DB yet
            const prefMode = localStorage.getItem("preferred_mode");
            if (!prefMode) {
                authScreen.classList.remove("hidden");
                showAuthView("account-choice-view");
            }
        }
    } else {
        console.log("User not logged in, showing initial auth screen.");
        authScreen.classList.remove("hidden");
        userNav.classList.add("hidden");
        dashboardScreen.classList.add("hidden");
        settingsScreen.classList.add("hidden");
        showAuthView("initial-auth-view");
        linkedPhone = "";
        sharedOwners = [];
    }
}

auth.onAuthStateChanged(handleAuthStateChange);

// --- Event Listeners ---

// Auth Navigation
if (showLoginBtn) showLoginBtn.addEventListener("click", () => showAuthView("login-view"));
if (showSignupBtn) showSignupBtn.addEventListener("click", () => showAuthView("signup-view"));
backToAuthBtns.forEach(btn => btn.addEventListener("click", () => showAuthView("initial-auth-view")));

const googleLegacyBtn = document.getElementById("google-login-btn-legacy");
if (googleLegacyBtn) {
    googleLegacyBtn.addEventListener("click", () => {
        showAuthView("login-view");
        googleLoginBtn.click();
    });
}

// Firebase Auth Actions
if (googleLoginBtn) {
    googleLoginBtn.addEventListener("click", async () => {
        try {
            setAuthOutput("מתחבר עם Google...");
            // Switch to signInWithRedirect to avoid COOP issues and improve mobile experience
            await auth.signInWithRedirect(googleProvider);
        } catch (e) {
            console.error("Login error:", e);
            setAuthOutput(`שגיאת התחברות: ${e.message}`);
        }
    });
}

if (emailLoginBtn) {
    emailLoginBtn.addEventListener("click", async () => {
        const email = loginEmailInput.value.trim();
        const password = loginPasswordInput.value;
        if (!email || !password) return setAuthOutput("נא להזין אימייל וסיסמה.");
        try {
            setAuthOutput("מתחבר...");
            await auth.signInWithEmailAndPassword(email, password);
        } catch (e) { setAuthOutput(`שגיאה: ${e.message}`); }
    });
}

if (emailSignupBtn) {
    emailSignupBtn.addEventListener("click", async () => {
        const email = signupEmailInput.value.trim();
        const password = signupPasswordInput.value;
        if (!email || !password) return setAuthOutput("נא להזין אימייל וסיסמה.");
        if (password.length < 6) return setAuthOutput("הסיסמה חייבת להיות לפחות 6 תווים.");
        try {
            setAuthOutput("יוצר חשבון...");
            await auth.createUserWithEmailAndPassword(email, password);
        } catch (e) { setAuthOutput(`שגיאת הרשמה: ${e.message}`); }
    });
}

// Mode Selection
if (choosePersonalBtn) {
    choosePersonalBtn.addEventListener("click", () => {
        localStorage.setItem("preferred_mode", "personal");
        handleAuthStateChange(auth.currentUser);
    });
}

if (chooseTherapistBtn) {
    chooseTherapistBtn.addEventListener("click", () => {
        localStorage.setItem("preferred_mode", "therapist");
        handleAuthStateChange(auth.currentUser);
    });
}

// WhatsApp OTP Auth Flow
if (authSendOtpBtn) {
    authSendOtpBtn.addEventListener("click", async () => {
        const phone = authPhoneInput.value.trim();
        if (!phone) return setAuthOutput("נא להזין מספר טלפון.");
        const shareToken = localStorage.getItem("pending_share_token");
        try {
            setAuthOutput("שולח קוד לוואטסאפ...");
            await callBotAction("request_otp", { phone, share_token: shareToken }, true);
            authPhoneWrap.classList.add("hidden");
            authOtpWrap.classList.remove("hidden");
            setAuthOutput("✅ הקוד נשלח!");
        } catch (e) { setAuthOutput(`שגיאה: ${e.message}`); }
    });
}

if (authVerifyOtpBtn) {
    authVerifyOtpBtn.addEventListener("click", async () => {
        const otp = authOtpInput.value.trim();
        const phone = authPhoneInput.value.trim();
        if (otp.length !== 6) return setAuthOutput("נא להזין קוד בן 6 ספרות.");
        try {
            setAuthOutput("מאמת קוד...");
            const res = await callBotAction("verify_otp", { phone, otp }, true);
            if (res.customToken) {
                setAuthOutput("✅ האימות הצליח! מתחבר...");
                await auth.signInWithCustomToken(res.customToken);
                localStorage.removeItem("pending_share_token");
                // After signInWithCustomToken, onAuthStateChanged will trigger and handle the rest
            } else {
                throw new Error("לא התקבל מפתח גישה מהשרת");
            }
        } catch (e) { setAuthOutput(`שגיאה: ${e.message}`); }
    });
}

if (authBackToPhoneBtn) {
    authBackToPhoneBtn.addEventListener("click", () => {
        authOtpWrap.classList.add("hidden");
        authPhoneWrap.classList.remove("hidden");
    });
}

if (authBackToChoiceBtn) {
    authBackToChoiceBtn.addEventListener("click", () => {
        localStorage.removeItem("preferred_mode");
        showAuthView("account-choice-view");
    });
}

// Global Nav
if (logoutBtn) {
    logoutBtn.addEventListener("click", async () => {
        await auth.signOut();
        localStorage.removeItem("preferred_mode");
        window.location.reload();
    });
}

// Nav Handlers
console.log("Setting up nav handlers...");
if (navDashboardBtn) navDashboardBtn.addEventListener("click", (e) => {
    e.preventDefault();
    showScreen("dashboard");
});
if (navPlannerBtn) navPlannerBtn.addEventListener("click", (e) => {
    e.preventDefault();
    console.log("Planner button clicked");
    showScreen("planner");
});
if (navSettingsBtn) navSettingsBtn.addEventListener("click", (e) => {
    e.preventDefault();
    showScreen("settings");
});
if (navSwitchModeBtn) navSwitchModeBtn.addEventListener("click", () => {
    localStorage.removeItem("preferred_mode");
    window.location.reload();
});

// --- Dashboard Features ---

if (sharedOwnerSelect) {
    sharedOwnerSelect.addEventListener("change", () => {
        const p = sharedOwnerSelect.value;
        if (p) loadSharedInsights(p);
    });
}

if (coachSendWorkoutBtn) {
    coachSendWorkoutBtn.addEventListener("click", async () => {
        const ownerPhone = sharedOwnerSelect.value;
        if (!ownerPhone) return;
        setOutput("שולח המלצת וויסות...", "loading");
        try {
            await callBotAction("coach_send_workout", { owner_phone: ownerPhone });
            setOutput("✅ המלצת וויסות נשלחה למטופל/ת!");
        } catch (e) { setOutput(`שגיאה: ${e.message}`); }
    });
}

if (syncDataBtn) {
    syncDataBtn.addEventListener("click", async () => {
        const ownerPhone = sharedOwnerSelect.value;
        const icon = syncDataBtn.querySelector('i');
        if (icon) icon.classList.add("animate-spin");
        setOutput("מסנכרן נתונים...", "loading");
        try {
            const res = await callBotAction("sync_data", { owner_phone: ownerPhone });
            setOutput(res.summary || "✅ הסנכרון הושלם.");
            await loadSharedInsights(ownerPhone);
        } catch (e) { setOutput(`שגיאה: ${e.message}`); }
        finally { if (icon) icon.classList.remove("animate-spin"); }
    });
}

if (userSyncDataBtn) {
    userSyncDataBtn.addEventListener("click", async () => {
        const icon = userSyncDataBtn.querySelector('i');
        if (icon) icon.classList.add("animate-spin");
        setOutput("מסנכרן נתונים...", "loading");
        try {
            const res = await callBotAction("sync_data");
            setOutput(res.summary || "✅ הסנכרון הושלם.");
            await loadUserInsights();
        } catch (e) { setOutput(`שגיאה: ${e.message}`); }
        finally { if (icon) icon.classList.remove("animate-spin"); }
    });
}

// Advanced Settings & Builder
if (saveSiteSettingsBtn) {
    saveSiteSettingsBtn.addEventListener("click", async () => {
        const ownerPhone = viewerMode ? sharedOwnerSelect.value : null;
        const wa_graph_metrics = Array.from(document.querySelectorAll('input[name="wa-metric"]:checked')).map(cb => cb.value);
        const settings = { 
            wa_graph_metrics, 
            notification_hours: { morning: notifMorningInput.value, evening: notifEveningInput.value }, 
            excluded_workouts: Array.from(document.querySelectorAll('.workout-toggle:not(:checked)')).map(cb => cb.value) 
        };
        setOutput("שומר הגדרות...", "loading");
        try {
            await callBotAction("update_site_settings", { owner_phone: ownerPhone, settings });
            setOutput("✅ הגדרות המערכת נשמרו.");
        } catch (e) { setOutput(`שגיאה: ${e.message}`); }
    });
}

if (saveCustomWorkoutBtn) {
    saveCustomWorkoutBtn.addEventListener("click", async () => {
        const ownerPhone = viewerMode ? sharedOwnerSelect.value : null;
        const workout = { id: wbId.value.trim(), name: wbName.value.trim(), nervous_system_state: wbState.value, duration_minutes: Number(wbDuration.value), short_description: wbDesc.value.trim(), full_description: wbFull.value.trim(), is_custom: true };
        if (!workout.id || !workout.name) return setOutput("נא למלא מזהה ושם.");
        setOutput("שומר אימון...", "loading");
        try {
            await callBotAction("save_custom_workout", { owner_phone: ownerPhone, workout });
            setOutput("✅ האימון נשמר!");
            wbId.value = ""; wbName.value = ""; wbDuration.value = ""; wbDesc.value = ""; wbFull.value = "";
            loadAdvancedSettings(ownerPhone);
        } catch (e) { setOutput(`שגיאה: ${e.message}`); }
    });
}

// ... Additional helper functions (populateSharedOwners, loadAdvancedSettings, renderCustomWorkouts, renderAnalysis, updateStatsGrid, renderMetricsChart, updateHistoryLists, setActiveRangeButton, loadSharedInsights) ...

function populateSharedOwners(owners) {
    if (!sharedOwnerSelect) return;
    sharedOwnerSelect.innerHTML = '<option value="">בחר/י מטופל/ת</option>';
    owners.forEach(o => {
        const opt = document.createElement("option");
        opt.value = o.phone || "";
        opt.textContent = o.name ? `${o.name} (${o.phone})` : o.phone;
        sharedOwnerSelect.appendChild(opt);
    });
}

async function loadAdvancedSettings(ownerPhone = null) {
    try {
        const data = await callBotAction("get_site_settings", { owner_phone: ownerPhone });
        const settings = data.settings || {};
        const catalog = data.catalog || [];
        const waMetrics = settings.wa_graph_metrics || ["hrv", "sleep", "energy", "workouts"];
        document.querySelectorAll('input[name="wa-metric"]').forEach(cb => cb.checked = waMetrics.includes(cb.value));
        if (notifMorningInput) notifMorningInput.value = settings.notification_hours?.morning || "08:00";
        if (notifEveningInput) notifEveningInput.value = settings.notification_hours?.evening || "20:00";
        if (workoutListSettings) {
            const excluded = settings.excluded_workouts || [];
            workoutListSettings.innerHTML = catalog.map(w => `
                <label class="flex items-center justify-between p-2 bg-slate-50 rounded-lg hover:bg-slate-100 transition-all cursor-pointer">
                    <span class="text-xs text-slate-600">${w.name} (${w.duration_minutes} דק')</span>
                    <input type="checkbox" value="${w.id}" ${!excluded.includes(w.id) ? 'checked' : ''} class="workout-toggle accent-[#5a7d6a]" />
                </label>`).join('');
        }
        renderCustomWorkouts(catalog.filter(w => w.is_custom), ownerPhone);
    } catch (e) { console.error("Advanced settings error:", e); }
}

function renderCustomWorkouts(customs, ownerPhone) {
    if (!customWorkoutsList) return;
    customWorkoutsList.innerHTML = customs.length ? customs.map(w => `
        <div class="p-4 rounded-2xl bg-slate-50 border border-slate-100 flex justify-between items-center">
            <div>
                <div class="font-bold text-slate-700">${w.name}</div>
                <div class="text-xs text-slate-400">${w.duration_minutes} דק' | ${w.nervous_system_state}</div>
            </div>
            <button class="delete-workout-btn text-rose-500 hover:text-rose-700 transition-colors p-2" data-id="${w.id}">
                <i data-lucide="trash-2" class="w-4 h-4"></i>
            </button>
        </div>`).join('') : '<div class="text-center text-slate-400 py-4 italic text-sm">אין אימונים מותאמים אישית</div>';
    if (typeof lucide !== 'undefined') lucide.createIcons();
    document.querySelectorAll(".delete-workout-btn").forEach(btn => {
        btn.addEventListener("click", async () => {
            const workoutId = btn.getAttribute("data-id");
            if (confirm("האם למחוק את האימון?")) {
                try {
                    await callBotAction("delete_custom_workout", { owner_phone: ownerPhone, workout_id: workoutId });
                    loadAdvancedSettings(ownerPhone);
                } catch (e) { setOutput(`שגיאה: ${e.message}`); }
            }
        });
    });
}

function renderAnalysis(analysis, deepReport = null) {
    if (!analysisSummary) return;
    if (!analysis) {
        analysisSummary.textContent = "אין נתונים מספיקים.";
        return;
    }
    let html = analysis.notes?.summary || "ניתוח הושלם.";
    if (deepReport) {
        html += `<div class="mt-6 p-6 bg-indigo-50/50 rounded-[24px] border border-indigo-100/50 text-slate-700 prose prose-slate max-w-none">
            <h4 class="text-indigo-600 font-bold mb-3 flex items-center gap-2"><i data-lucide="sparkles" class="w-4 h-4"></i>דוח עומק שבועי (AI)</h4>
            <div class="whitespace-pre-wrap text-sm leading-relaxed text-right" dir="rtl">${deepReport}</div>
        </div>`;
    }
    analysisSummary.innerHTML = html;
    if (typeof lucide !== 'undefined') lucide.createIcons();
    if (analysisPhysical) analysisPhysical.textContent = analysis.notes?.physical || "—";
    if (analysisSleep) analysisSleep.textContent = analysis.notes?.sleep || "—";
    if (analysisSurveys) analysisSurveys.textContent = analysis.notes?.questionnaires || "—";
    if (analysisState) analysisState.textContent = analysis.state?.label || "—";
    if (analysisNightmares) analysisNightmares.textContent = analysis.notes?.nightmares || "—";
    if (analysisHrvThreshold) analysisHrvThreshold.textContent = analysis.notes?.hrv_threshold || "—";
}

function updateStatsGrid(rows) {
    const avg = arr => {
        const nums = arr.filter(v => typeof v === "number");
        return nums.length ? (nums.reduce((a, b) => a + b, 0) / nums.length).toFixed(1) : "--";
    };
    document.getElementById("avg-mood").textContent = avg(rows.map(r => r.survey_0));
    document.getElementById("avg-energy").textContent = avg(rows.map(r => r.survey_1));
    document.getElementById("avg-weather").textContent = avg(rows.map(r => r.survey_3));
    document.getElementById("avg-workout").textContent = avg(rows.map(r => r.workout_minutes));
}

function renderMetricsChart(rows) {
    const ctx = document.getElementById("metrics-chart").getContext('2d');
    const labels = rows.map(r => String(r.id || "").slice(5));
    const hrv = rows.map(r => r.hrv_consistent || r.hrv || r.hrv_sdnn || null);
    const sleep = rows.map(r => (r.sleepSecs ? +(r.sleepSecs / 3600).toFixed(1) : null));
    const stress = rows.map(r => r.survey_1 !== undefined ? r.survey_1 * 10 : null);
    const heartRate = rows.map(r => r.resting_hr || r.avg_hr || null);
    const workoutDone = rows.map(r => r.workout_count > 0 || r.has_workout ? 100 : 0);
    if (metricsChart) metricsChart.destroy();
    metricsChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [
                { label: 'HRV', data: hrv, borderColor: '#60a5fa', backgroundColor: 'rgba(96, 165, 250, 0.1)', fill: true, tension: 0.4, yAxisID: 'y' },
                { label: 'שינה', data: sleep, borderColor: '#a855f7', backgroundColor: 'rgba(168, 85, 247, 0.1)', fill: true, tension: 0.4, yAxisID: 'y_sleep' },
                { label: 'אנרגיה', data: stress, borderColor: '#f59f00', borderDash: [5, 5], fill: false, tension: 0.1, yAxisID: 'y' },
                { label: 'דופק', data: heartRate, borderColor: '#ef4444', backgroundColor: 'rgba(239, 68, 68, 0.1)', fill: false, tension: 0.3, yAxisID: 'y_hr' },
                { label: 'וויסות', data: workoutDone, type: 'bar', backgroundColor: 'rgba(34, 197, 94, 0.3)', borderColor: '#22c55e', borderWidth: 1, yAxisID: 'y_workout' }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { color: '#94a3b8', font: { family: 'Assistant' }, usePointStyle: true } },
                tooltip: { mode: 'index', intersect: false, backgroundColor: '#1e293b', titleColor: '#f8fafc', bodyColor: '#cbd5e1' }
            },
            scales: {
                x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#64748b' } },
                y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#64748b' }, title: { display: true, text: 'HRV / אנרגיה' } },
                y_sleep: { position: 'right', grid: { display: false }, ticks: { color: '#a855f7' }, title: { display: true, text: 'שעות שינה' }, min: 0, max: 15 },
                y_hr: { position: 'right', grid: { display: false }, ticks: { color: '#ef4444' }, title: { display: true, text: 'דופק' }, min: 40, max: 100 },
                y_workout: { display: false, min: 0, max: 100 }
            }
        }
    });
}

function updateHistoryLists(rows, recs) {
    const recWrap = document.getElementById("last-recommendations");
    recWrap.innerHTML = recs.length ? recs.slice(0, 3).map(r => `
        <div class="p-4 rounded-xl bg-slate-800/50 border border-slate-700/50 flex justify-between items-center group hover:bg-slate-800 transition-all">
            <div><div class="font-bold text-blue-400">${r.name || 'אימון'}</div><div class="text-xs text-slate-500">${r.short_description || ''}</div></div>
            <i data-lucide="chevron-left" class="w-4 h-4 text-slate-600 group-hover:text-blue-500 transition-colors"></i>
        </div>`).join('') : '<div class="text-center text-slate-500 py-4 italic">אין המלצות</div>';
    const surveyWrap = document.getElementById("survey-summary");
    surveyWrap.innerHTML = rows.length ? rows.slice(-3).reverse().map(r => `
        <div class="p-3 rounded-xl bg-slate-800/30 border border-slate-700/30 flex items-center justify-between">
            <div class="text-xs font-mono text-slate-500">${r.id}</div>
            <div class="flex gap-4 text-xs font-medium">
                <span class="text-green-400">😊 ${r.survey_0 || '-'}</span>
                <span class="text-blue-400">⚡ ${r.survey_1 || '-'}</span>
                <span class="text-yellow-400">🌤️ ${r.survey_3 || '-'}</span>
            </div>
        </div>`).join('') : '<div class="text-center text-slate-500 py-4 italic">אין דיווחים</div>';
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

async function loadSharedInsights(ownerPhone) {
    if (!ownerPhone) return;
    try {
        setOutput("טוען נתונים למעקב...", "loading");
        const data = await callBotAction("fetch_shared_insights", { owner_phone: ownerPhone, range_days: currentRangeDays });
        if (viewOtpSection) viewOtpSection.classList.add("hidden");
        if (coachActionsArea) coachActionsArea.classList.remove("hidden");
        if (syncDataBtn) syncDataBtn.classList.remove("hidden");
        const rows = data.rows || [];
        const recs = data.recs || [];
        updateStatsGrid(rows);
        renderMetricsChart(rows);
        updateHistoryLists(rows, recs);
        renderAnalysis(data.analysis, data.deep_report);
        if (therapistDetailsArea) therapistDetailsArea.classList.remove("hidden");
        if (therapistHistoryTable) {
            therapistHistoryTable.innerHTML = rows.slice().reverse().map(r => `
                <tr class="border-b border-slate-50 hover:bg-slate-50 transition-all">
                    <td class="py-3 text-slate-500 font-mono text-xs">${r.id}</td>
                    <td class="py-3 text-rose-500 font-bold">${r.survey_0 || '-'}</td>
                    <td class="py-3 text-indigo-500 font-bold">${r.survey_1 || '-'}</td>
                    <td class="py-3 text-slate-600">${r.sleepSecs ? (r.sleepSecs / 3600).toFixed(1) + 'h' : '-'}</td>
                    <td class="py-3 text-rose-600">${r.resting_hr || '-'}</td>
                    <td class="py-3 text-blue-500 font-bold">${r.hrv_consistent || r.hrv || '-'}</td>
                </tr>`).join('');
        }
        setOutput(`נתוני ${data.owner?.name || 'המטופל'} נטענו.`);
        loadAdvancedSettings(ownerPhone);
    } catch (e) {
        if (e.message === "verification_required") {
            setOutput("נדרש אימות וואטסאפ לצפייה.");
            if (viewOtpSection) {
                viewOtpSection.classList.remove("hidden");
                requestViewOtpWrap.classList.remove("hidden");
                verifyViewOtpWrap.classList.add("hidden");
            }
        } else setOutput(`שגיאה: ${e.message}`);
    }
}

// Profile Save
if (saveProfileBtn) {
    saveProfileBtn.addEventListener("click", async () => {
        const payload = { 
            name: document.getElementById("profile-name").value.trim(), 
            gender: document.getElementById("profile-gender").value, 
            intervals_athlete_id: document.getElementById("profile-athlete").value.trim(), 
            intervals_api_key: document.getElementById("profile-key").value.trim(), 
            emergency_name: document.getElementById("profile-emergency-name").value.trim(), 
            emergency_phone: document.getElementById("profile-emergency-phone").value.trim() 
        };
        try {
            await callBotAction("register", payload);
            setOutput("✅ פרופיל עודכן.");
            loadAdvancedSettings();
        } catch (e) { setOutput(`שגיאה: ${e.message}`); }
    });
}

// --- Therapist View OTP Listeners ---
if (requestViewOtpBtn) {
    requestViewOtpBtn.addEventListener("click", async () => {
        const ownerPhone = sharedOwnerSelect.value;
        if (!ownerPhone) return;
        try {
            setOutput("שולח קוד אימות לוואטסאפ שלך...", "loading");
            await callBotAction("request_view_otp", { owner_phone: ownerPhone });
            requestViewOtpWrap.classList.add("hidden");
            verifyViewOtpWrap.classList.remove("hidden");
            setOutput("✅ הקוד נשלח לוואטסאפ שלך.");
        } catch (e) { setOutput(`שגיאה: ${e.message}`); }
    });
}

if (verifyViewOtpBtn) {
    verifyViewOtpBtn.addEventListener("click", async () => {
        const ownerPhone = sharedOwnerSelect.value;
        const otp = viewOtpInput.value.trim();
        if (!ownerPhone || otp.length !== 6) return setOutput("נא להזין קוד בן 6 ספרות.");
        try {
            setOutput("מאמת קוד...", "loading");
            await callBotAction("verify_view_otp", { owner_phone: ownerPhone, otp });
            setOutput("✅ האימות הצליח! טוען נתונים...");
            loadSharedInsights(ownerPhone);
        } catch (e) { setOutput(`שגיאה: ${e.message}`); }
    });
}

if (changeViewOwnerBtn) {
    changeViewOwnerBtn.addEventListener("click", () => {
        viewOtpSection.classList.add("hidden");
        setOutput("בחר/י מטופל/ת אחר/ת.");
    });
}

// --- Dashboard WhatsApp Link Listeners ---
const dashSendOtpBtn = document.getElementById("send-otp-btn");
const dashVerifyOtpBtn = document.getElementById("verify-otp-btn");
const dashPhoneInput = document.getElementById("login-phone");
const dashOtpInput = document.getElementById("otp-input");
const dashPhoneView = document.getElementById("phone-view");
const dashOtpView = document.getElementById("otp-view");
const dashBackToPhone = document.getElementById("back-to-phone");

if (dashSendOtpBtn) {
    dashSendOtpBtn.addEventListener("click", async () => {
        const phone = dashPhoneInput.value.trim();
        if (!phone) return setOutput("נא להזין מספר טלפון.");
        try {
            setOutput("שולח קוד לוואטסאפ...", "loading");
            await callBotAction("request_otp", { phone }, true);
            dashPhoneView.classList.add("hidden");
            dashOtpView.classList.remove("hidden");
            setOutput("✅ הקוד נשלח!");
        } catch (e) { setOutput(`שגיאה: ${e.message}`); }
    });
}

if (dashVerifyOtpBtn) {
    dashVerifyOtpBtn.addEventListener("click", async () => {
        const otp = dashOtpInput.value.trim();
        const phone = dashPhoneInput.value.trim();
        if (otp.length !== 6) return setOutput("נא להזין קוד בן 6 ספרות.");
        try {
            setOutput("מאמת קוד...", "loading");
            await callBotAction("verify_otp", { phone, otp });
            setOutput("✅ האימות הצליח!");
            window.location.reload();
        } catch (e) { setOutput(`שגיאה: ${e.message}`); }
    });
}

if (dashBackToPhone) {
    dashBackToPhone.addEventListener("click", () => {
        dashOtpView.classList.add("hidden");
        dashPhoneView.classList.remove("hidden");
    });
}

// --- Share Management Listeners ---
const shareAddBtn = document.getElementById("share-add-btn");
if (shareAddBtn) {
    shareAddBtn.addEventListener("click", async () => {
        const phoneInput = document.getElementById("share-viewer-phone");
        const phone = phoneInput ? phoneInput.value.trim() : "";
        if (!phone) return setOutput("נא להזין מספר טלפון לשיתוף.");
        setOutput("יוצר קישור שיתוף ושולח בוואטסאפ...", "loading");
        try {
            await callBotAction("share_add_viewer", { phone });
            if (phoneInput) phoneInput.value = "";
            setOutput("✅ קישור השיתוף נשלח בהצלחה בוואטסאפ.");
            loadShareViewers();
        } catch (e) { setOutput(`שגיאה: ${e.message}`); }
    });
}

async function loadShareViewers() {
    try {
        const data = await callBotAction("share_list_viewers");
        const viewers = data.viewers || [];
        const wrap = document.getElementById("share-viewers-list");
        if (!wrap) return;
        wrap.innerHTML = viewers.length ? viewers.map(v => `
            <div class="flex items-center justify-between p-2 bg-slate-50 rounded-lg mt-2">
                <span>${v.phone || v.email}</span>
                <button class="remove-viewer-btn text-rose-500 hover:text-rose-700 p-1" data-phone="${v.phone || ''}" data-email="${v.email || ''}">
                    <i data-lucide="x-circle" class="w-4 h-4"></i>
                </button>
            </div>`).join('') : '<div class="text-xs text-slate-400 italic py-2">לא נוספו מורשי צפייה</div>';
        if (typeof lucide !== 'undefined') lucide.createIcons();
        document.querySelectorAll(".remove-viewer-btn").forEach(btn => {
            btn.addEventListener("click", async () => {
                const phone = btn.getAttribute("data-phone");
                const email = btn.getAttribute("data-email");
                const identifier = phone || email;
                if (confirm(`האם להסיר את ${identifier}?`)) {
                    try {
                        await callBotAction("share_remove_viewer", { phone, email });
                        loadShareViewers();
                    } catch (e) { setOutput(`שגיאה: ${e.message}`); }
                }
            });
        });
    } catch (e) { console.error("Share viewers error:", e); }
}

// WhatsApp Button Link
if (window.botWhatsAppNumber) {
    const btn = document.getElementById("bot-link-btn");
    if (btn) btn.addEventListener("click", () => {
        const msg = encodeURIComponent("חבר");
        window.open(`https://wa.me/${window.botWhatsAppNumber}?text=${msg}`, "_blank");
    });
}

// --- Workout Builder & Garmin Sync ---
let workoutMap, workoutPath, mapMarkers = [];
let workoutSteps = [
    { type: 'Warmup', duration: '10m', target: '60% HR', targetType: 'HR', targetValue: '60%' },
    { type: 'Active', duration: '30m', target: '70% HR', targetType: 'HR', targetValue: '70%' },
    { type: 'Cooldown', duration: '10m', target: '60% HR', targetType: 'HR', targetValue: '60%' }
];

function initWorkoutMap() {
    console.log("Initializing Workout Map...");
    if (typeof google === 'undefined' || typeof google.maps === 'undefined') {
        console.warn("Google Maps not loaded yet.");
        return;
    }
    const mapEl = document.getElementById("workout-map");
    if (!mapEl) {
        console.warn("Map element not found.");
        return;
    }
    if (workoutMap) return;
    
    workoutMap = new google.maps.Map(mapEl, {
        center: { lat: 32.0853, lng: 34.7818 }, // Tel Aviv default
        zoom: 13,
        disableDefaultUI: true,
        zoomControl: true,
        styles: [
            { "featureType": "poi", "stylers": [{ "visibility": "off" }] }
        ]
    });

    workoutPath = new google.maps.Polyline({
        strokeColor: "#5a7d6a",
        strokeOpacity: 0.8,
        strokeWeight: 4,
        map: workoutMap
    });

    workoutMap.addListener("click", (e) => {
        const path = workoutPath.getPath();
        path.push(e.latLng);
        
        const marker = new google.maps.Marker({
            position: e.latLng,
            map: workoutMap,
            icon: {
                path: google.maps.SymbolPath.CIRCLE,
                scale: 4,
                fillColor: "#5a7d6a",
                fillOpacity: 1,
                strokeWeight: 1
            }
        });
        mapMarkers.push(marker);
        updateMapInfo();
    });
    
    renderSteps();
}

function renderSteps() {
    const container = document.getElementById("steps-container");
    if (!container) return;
    
    const workoutType = document.getElementById("wb-type")?.value || "Run";
    const isBreathwork = workoutType === "Breathwork";
    
    container.innerHTML = workoutSteps.map((step, index) => {
        // Ensure step has targetType and durationType
        if (!step.targetType) step.targetType = step.target && step.target.includes('pace') ? 'Pace' : 'HR';
        if (!step.durationType) {
            if (step.duration.includes('km')) step.durationType = 'km';
            else if (step.duration.includes('s')) step.durationType = 's';
            else step.durationType = 'm';
        }
        
        let typeOptions = "";
        if (isBreathwork) {
            typeOptions = `
                <option value="Inhale" ${step.type === 'Inhale' ? 'selected' : ''}>שאיפה</option>
                <option value="Hold" ${step.type === 'Hold' ? 'selected' : ''}>עצירה</option>
                <option value="Exhale" ${step.type === 'Exhale' ? 'selected' : ''}>נשיפה</option>
                <option value="Recovery" ${step.type === 'Recovery' ? 'selected' : ''}>מנוחה</option>
            `;
        } else {
            typeOptions = `
                <option value="Warmup" ${step.type === 'Warmup' ? 'selected' : ''}>חימום</option>
                <option value="Active" ${step.type === 'Active' ? 'selected' : ''}>אינטרוול</option>
                <option value="Recovery" ${step.type === 'Recovery' ? 'selected' : ''}>התאוששות</option>
                <option value="Cooldown" ${step.type === 'Cooldown' ? 'selected' : ''}>שחרור</option>
            `;
        }

        return `
        <div class="flex flex-wrap items-center gap-2 bg-white p-3 rounded-2xl border border-slate-100 shadow-sm animate-in fade-in slide-in-from-right-2 duration-300">
            <div class="w-8 h-8 flex-shrink-0 bg-slate-50 rounded-lg flex items-center justify-center text-xs font-bold text-slate-400">${index + 1}</div>
            
            <select onchange="updateStep(${index}, 'type', this.value)" class="bg-slate-50 border-none rounded-lg text-[10px] font-bold text-slate-600 focus:ring-0">
                ${typeOptions}
            </select>

            <div class="flex items-center bg-slate-50 rounded-lg px-2">
                <input type="text" value="${step.duration.replace('m', '').replace('s', '').replace('km', '')}" 
                    onchange="updateStep(${index}, 'durationValue', this.value)" 
                    class="w-12 bg-transparent border-none text-[10px] text-center focus:ring-0" placeholder="10" />
                <select onchange="updateStep(${index}, 'durationType', this.value)" class="bg-transparent border-none text-[10px] font-bold text-slate-500 focus:ring-0">
                    <option value="m" ${step.durationType === 'm' ? 'selected' : ''}>דק'</option>
                    <option value="s" ${step.durationType === 's' ? 'selected' : ''}>שנ'</option>
                    <option value="km" ${step.durationType === 'km' ? 'selected' : ''}>ק"מ</option>
                </select>
            </div>

            ${!isBreathwork ? `
            <div class="flex items-center bg-slate-50 rounded-lg px-2">
                <select onchange="updateStep(${index}, 'targetType', this.value)" class="bg-transparent border-none text-[10px] font-bold text-slate-500 focus:ring-0">
                    <option value="HR" ${step.targetType === 'HR' ? 'selected' : ''}>דופק</option>
                    <option value="Pace" ${step.targetType === 'Pace' ? 'selected' : ''}>קצב</option>
                </select>
                <input type="text" value="${step.target.replace(' HR', '').replace(' pace', '')}" 
                    onchange="updateStep(${index}, 'targetValue', this.value)" 
                    class="w-20 bg-transparent border-none text-[10px] text-center focus:ring-0" 
                    placeholder="${step.targetType === 'HR' ? '70%' : '5:30'}" />
            </div>
            ` : ''}

            <button onclick="removeStep(${index})" class="text-slate-300 hover:text-rose-500 transition-colors p-1 mr-auto">
                <i data-lucide="trash-2" class="w-4 h-4"></i>
            </button>
        </div>
    `}).join('');
    
    if (typeof lucide !== 'undefined') lucide.createIcons();
    updateWorkoutPreview();
}

window.updateStep = function(index, field, value) {
    const step = workoutSteps[index];
    if (field === 'targetType' || field === 'targetValue') {
        if (field === 'targetType') step.targetType = value;
        if (field === 'targetValue') step.targetValue = value;
        const val = step.targetValue || step.target.replace(' HR', '').replace(' pace', '');
        step.target = step.targetType === 'HR' ? `${val} HR` : `${val} pace`;
    } else if (field === 'durationType' || field === 'durationValue') {
        if (field === 'durationType') step.durationType = value;
        if (field === 'durationValue') step.durationValue = value;
        const val = step.durationValue || step.duration.replace('m', '').replace('s', '').replace('km', '');
        step.duration = `${val}${step.durationType}`;
    } else {
        step[field] = value;
    }
    updateWorkoutPreview();
    if (field === 'targetType' || field === 'durationType') renderSteps();
};

window.removeStep = function(index) {
    workoutSteps.splice(index, 1);
    renderSteps();
};

function updateWorkoutPreview() {
    const preview = document.getElementById("workout-preview");
    if (!preview) return;
    
    const workoutType = document.getElementById("wb-type")?.value || "Run";
    const isBreathwork = workoutType === "Breathwork";
    
    const text = workoutSteps.map(s => {
        if (isBreathwork) {
            return `- ${s.type} ${s.duration}`;
        }
        return `- ${s.type} ${s.duration} ${s.target}`;
    }).join('\n');
    preview.textContent = text;
}

function updateMapInfo() {
    const path = workoutPath.getPath();
    const info = document.getElementById("map-info");
    const stats = document.getElementById("map-stats");
    if (!info) return;
    
    if (path.getLength() < 2) {
        info.textContent = 'לחיצה על המפה מוסיפה נקודה למסלול. המרחק יתעדכן אוטומטית באימון.';
        if (stats) stats.textContent = "";
        return;
    }
    
    const distMeters = google.maps.geometry.spherical.computeLength(path);
    const distKm = (distMeters / 1000).toFixed(2);
    info.innerHTML = `<button onclick="clearWorkoutMap()" class="text-rose-500 underline">נקה מסלול</button>`;
    if (stats) stats.textContent = `${distKm} ק"מ`;
    
    // Update the main "Active" step with the distance
    const activeIndex = workoutSteps.findIndex(s => s.type === 'Active');
    if (activeIndex !== -1) {
        workoutSteps[activeIndex].duration = `${distKm}km`;
        renderSteps();
    }
}

// Special Modes
const freezeBtn = document.getElementById("mode-freeze-btn");
if (freezeBtn) {
    freezeBtn.addEventListener("click", () => {
        workoutSteps = [
            { type: 'Warmup', duration: '5m', target: '50% HR', targetType: 'HR', targetValue: '50%' },
            { type: 'Active', duration: '1m', target: 'Vibrate Every 1m', targetType: 'HR', targetValue: 'Vibrate Every 1m' },
            { type: 'Active', duration: '1m', target: 'Vibrate Every 1m', targetType: 'HR', targetValue: 'Vibrate Every 1m' },
            { type: 'Active', duration: '1m', target: 'Vibrate Every 1m', targetType: 'HR', targetValue: 'Vibrate Every 1m' },
            { type: 'Cooldown', duration: '5m', target: '50% HR', targetType: 'HR', targetValue: '50%' }
        ];
        document.getElementById("wb-name").value = "Freeze Mode - Grounding Walk";
        renderSteps();
    });
}

const anxietyBtn = document.getElementById("mode-anxiety-btn");
if (anxietyBtn) {
    anxietyBtn.addEventListener("click", () => {
        workoutSteps = [
            { type: 'Warmup', duration: '10m', target: 'MAX 120 HR', targetType: 'HR', targetValue: 'MAX 120' },
            { type: 'Active', duration: '20m', target: 'MAX 135 HR', targetType: 'HR', targetValue: 'MAX 135' },
            { type: 'Cooldown', duration: '10m', target: 'MAX 115 HR', targetType: 'HR', targetValue: 'MAX 115' }
        ];
        document.getElementById("wb-name").value = "High Anxiety - HR Cap Session";
        renderSteps();
    });
}

window.clearWorkoutMap = function() {
    if (workoutPath) workoutPath.setPath([]);
    mapMarkers.forEach(m => m.setMap(null));
    mapMarkers = [];
    updateMapInfo();
};

const syncToGarminBtn = document.getElementById("sync-to-garmin-btn");
if (syncToGarminBtn) {
    syncToGarminBtn.addEventListener("click", async () => {
        const name = document.getElementById("wb-name").value || "SportTrauma Workout";
        const desc = document.getElementById("wb-desc").value || "";
        const type = document.getElementById("wb-type").value || "Run";
        
        const now = new Date();
        const localIso = new Date(now.getTime() - (now.getTimezoneOffset() * 60000)).toISOString().slice(0, 19);

        // Map UI steps to Intervals.icu format (plain text description)
        const workoutText = workoutSteps.map(s => `- ${s.type} ${s.duration} ${s.target}`).join('\n');

        const workoutData = {
            category: "WORKOUT",
            type: type,
            start_date_local: localIso,
            name: name,
            description: workoutText + (desc ? `\n\nNotes: ${desc}` : ""),
            workout: {
                // For simplicity, we send the steps as text in description which Intervals handles, 
                // but we can also build the complex JSON steps here if needed.
                // Intervals.icu is very good at parsing the text format.
            }
        };

        setOutput("שולח לשעון (Garmin)...", "loading");
        try {
            await callBotAction("sync_workout_garmin", { workout_data: workoutData });
            setOutput("✅ האימון נשלח בהצלחה! הוא יופיע ביומן הגרמין שלך תוך שניות.");
            alert("✅ האימון נשלח בהצלחה לגרמין!");
        } catch (e) {
            setOutput(`שגיאה בסנכרון: ${e.message}`);
        }
    });
}

// Initialize
function initApp() {
    console.log("App initialization started...");
    initRangeButtons();
    initWorkoutMap();
    
    // Setup workout builder listeners
    const wbType = document.getElementById("wb-type");
    if (wbType) {
        wbType.addEventListener("change", () => {
            console.log("Workout type changed to:", wbType.value);
            const isBreathwork = wbType.value === "Breathwork";
            if (isBreathwork) {
                workoutSteps = [
                    { type: 'Inhale', duration: '4s', target: '', targetType: 'HR', targetValue: '' },
                    { type: 'Hold', duration: '4s', target: '', targetType: 'HR', targetValue: '' },
                    { type: 'Exhale', duration: '4s', target: '', targetType: 'HR', targetValue: '' },
                    { type: 'Hold', duration: '4s', target: '', targetType: 'HR', targetValue: '' }
                ];
            }
            renderSteps();
        });
    }

    const addStepBtn = document.getElementById("add-step-btn");
    if (addStepBtn) {
        addStepBtn.addEventListener("click", () => {
            const isBreathwork = document.getElementById("wb-type")?.value === "Breathwork";
            if (isBreathwork) {
                workoutSteps.push({ type: 'Inhale', duration: '4s', target: '', targetType: 'HR', targetValue: '' });
            } else {
                workoutSteps.push({ 
                    type: 'Active', 
                    duration: '5m', 
                    target: '75% HR',
                    targetType: 'HR',
                    targetValue: '75%'
                });
            }
            renderSteps();
        });
    }

    console.log("Attaching data-action listeners...");
    document.querySelectorAll('[data-action]').forEach(btn => {
        console.log("Attaching listener to button with action:", btn.getAttribute('data-action'));
        btn.addEventListener('click', async () => {
            const action = btn.getAttribute('data-action');
            if (!action) return;
            
            const icon = btn.querySelector('i');
            if (icon) icon.classList.add('animate-spin');
            setOutput("מעבד בקשה...", "loading");
            
            try {
                const res = await callBotAction(action);
                if (action === "calendar_link" && res.link) {
                    window.open(res.link, "_blank");
                    setOutput("פתחתי את דף החיבור ליומן בחלון חדש.");
                } else if (res.summary) {
                    setOutput(res.summary);
                } else {
                    setOutput("✅ הפעולה בוצעה בהצלחה.");
                }
            } catch (e) {
                if (e.message === "not_connected_to_intervals") {
                    setOutput("יש לחבר את Intervals.icu בהגדרות כדי לקבל המלצת אימון.");
                    showScreen("settings");
                } else {
                    setOutput(`שגיאה: ${e.message}`);
                }
            } finally {
                if (icon) icon.classList.remove('animate-spin');
            }
        });
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}

auth.getRedirectResult().catch(e => {
    console.error("Redirect error:", e);
    if (e.code === 'auth/cross-origin-opener-policy-blocked') {
        setAuthOutput("שגיאת דפדפן: COOP. נא לרענן.");
    }
});
