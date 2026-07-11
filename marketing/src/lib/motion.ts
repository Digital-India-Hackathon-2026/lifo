import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { CustomEase } from "gsap/CustomEase";

gsap.registerPlugin(ScrollTrigger, CustomEase);

// Named, weighted curves — replace every default browser ease/ease-out in this project.
// kavachSettle: decisive weighted deceleration, no overshoot (section reveals, text)
// kavachSpring: slight overshoot then settle (magnetic snap-back, button press release)
// kavachDrift : steep weighted in-out (scroll-scrubbed motion, continuous drag)
CustomEase.create("kavachSettle", "M0,0 C0.16,1 0.3,1 1,1");
CustomEase.create("kavachSpring", "M0,0 C0.34,1.56 0.64,1 1,1");
CustomEase.create("kavachDrift", "M0,0 C0.83,0 0.17,1 1,1");

export { gsap, ScrollTrigger };
