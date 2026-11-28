import Icon, { Logo } from "./Icon";

export default function HeroPreview() {
  return (
    <div className="relative mx-auto w-full max-w-[490px] select-none" aria-hidden="true">
      {/* Main soft sage frame */}
      <div className="hero-img relative overflow-hidden rounded-[28px] border border-white/80 bg-gradient-to-br from-[#F3F8F5] via-[#E9F3ED] to-[#DFECE4] px-6 py-9 shadow-[0_30px_70px_-28px_rgba(16,56,42,0.28)] sm:px-10 sm:py-11">
        {/* Ambient soft glow */}
        <div className="pointer-events-none absolute -right-10 -top-10 h-44 w-44 rounded-full bg-[#BFE5D2]/45 blur-2xl" />
        <div className="pointer-events-none absolute -bottom-10 left-4 h-40 w-40 rounded-full bg-[#C9E7D7]/50 blur-2xl" />

        {/* Subtle botanical leaves (top right & bottom right) */}
        <svg className="pointer-events-none absolute right-2 top-3 h-28 w-28 text-[#8EBFA8]/55" viewBox="0 0 120 120" fill="currentColor">
          <path d="M62 110c-2-36 14-66 44-88-10 38-20 68-44 88Z" opacity="0.5" />
          <path d="M56 106c-14-24-12-52 8-76 4 28 2 52-8 76Z" opacity="0.35" />
        </svg>
        <svg className="pointer-events-none absolute bottom-3 right-3 h-40 w-28 text-[#7FB69B]/55" viewBox="0 0 120 170" fill="currentColor">
          <path d="M40 162c6-48 22-94 52-136" stroke="currentColor" strokeWidth="2.5" fill="none" strokeLinecap="round" />
          <ellipse cx="75" cy="64" rx="18" ry="8" transform="rotate(-38 75 64)" opacity="0.55" />
          <ellipse cx="44" cy="84" rx="17" ry="7.5" transform="rotate(28 44 84)" opacity="0.45" />
          <ellipse cx="72" cy="108" rx="19" ry="8" transform="rotate(-32 72 108)" opacity="0.55" />
          <ellipse cx="40" cy="126" rx="16" ry="7" transform="rotate(25 40 126)" opacity="0.4" />
        </svg>
        <svg className="pointer-events-none absolute bottom-10 left-10 h-28 w-24 text-[#93C3AC]/45" viewBox="0 0 100 120" fill="currentColor">
          <ellipse cx="38" cy="70" rx="16" ry="7" transform="rotate(-48 38 70)" />
          <ellipse cx="58" cy="46" rx="14" ry="6" transform="rotate(-24 58 46)" opacity="0.7" />
        </svg>

        {/* Subtle neural network graph floating left */}
        <svg className="pointer-events-none absolute left-6 top-20 hidden h-28 w-28 text-[#598F78]/45 sm:block" viewBox="0 0 120 120" fill="none">
          <g stroke="currentColor" strokeWidth="1">
            <path d="M18 60L54 28M18 60L54 60M18 60L54 92M54 28L92 42M54 28L92 78M54 60L92 42M54 60L92 78M54 92L92 42M54 92L92 78" />
          </g>
          {[[18, 60], [54, 28], [54, 60], [54, 92], [92, 42], [92, 78]].map(([cx, cy]) => (
            <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="4" fill="#EAF4EE" stroke="currentColor" strokeWidth="1.4" />
          ))}
        </svg>

        {/* Soft accent dots */}
        <span className="pointer-events-none absolute left-10 top-1/2 h-2.5 w-2.5 rounded-full bg-[#8AD1B0]/70" />
        <span className="pointer-events-none absolute bottom-20 left-8 h-2 w-2 rounded-full bg-[#9BD9BC]/70" />
        <span className="pointer-events-none absolute right-8 top-1/2 h-2.5 w-2.5 rounded-full bg-[#92D1B2]/70" />

        {/* Smartphone mockup */}
        <div className="relative z-10 mx-auto w-[228px] rounded-[34px] border-[7px] border-[#152821] bg-gradient-to-b from-[#FAFDFB] via-[#DCECE4] to-[#C6DED1] shadow-[0_24px_48px_-18px_rgba(14,45,33,0.45)] sm:w-[244px]">
          {/* Status bar & notch */}
          <div className="relative flex items-center justify-between px-4 pb-1 pt-2.5 text-[10px] font-semibold text-[#183328]">
            <span>9:41</span>
            <span className="h-3.5 w-16 rounded-full bg-[#152821]" />
            <span className="flex items-center gap-1">
              <span className="inline-block h-2 w-2.5 rounded-[2px] border border-[#183328]" />
            </span>
          </div>

          {/* App logo inside screen */}
          <div className="flex justify-center pb-2 pt-2">
            <Logo size={32} />
          </div>

          {/* Scan reticle & lesion visualization */}
          <div className="relative mx-3 my-1 flex h-[178px] items-center justify-center rounded-2xl bg-gradient-to-b from-[#8CA99D]/25 via-[#A5B4A8]/35 to-[#B69B8A]/35">
            {/* Concentric scan rings */}
            <div className="absolute h-36 w-36 rounded-full border border-white/45" />
            <div className="absolute h-28 w-28 rounded-full border-2 border-white/70 bg-white/10" />
            <div className="absolute h-20 w-20 rounded-full border border-[#52B788]/55 bg-gradient-to-br from-[#F0D5C1]/85 via-[#DFB79E]/75 to-[#CFA085]/80 shadow-inner" />
            {/* Inner target circle */}
            <div className="relative h-12 w-12 rounded-full bg-gradient-to-br from-[#D79F82]/85 to-[#B57B61]/80 ring-2 ring-white/80" />

            {/* Viewfinder corner brackets */}
            <span className="absolute left-3 top-3 h-5 w-5 rounded-tl-md border-l-2 border-t-2 border-white/85" />
            <span className="absolute right-3 top-3 h-5 w-5 rounded-tr-md border-r-2 border-t-2 border-white/85" />
            <span className="absolute bottom-3 left-3 h-5 w-5 rounded-bl-md border-b-2 border-l-2 border-white/85" />
            <span className="absolute bottom-3 right-3 h-5 w-5 rounded-br-md border-b-2 border-r-2 border-white/85" />
          </div>

          {/* Bottom white status sheet */}
          <div className="relative mt-2 rounded-b-[27px] rounded-t-2xl bg-white/95 px-4 pb-3.5 pt-5 text-[11px] text-[#28473A]">
            {/* Quality clear pill overlapping sheet top */}
            <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-[#24825C] px-3.5 py-1 text-[11px] font-semibold text-white shadow-md">
              <span className="inline-flex items-center gap-1.5">
                <Icon name="check" size={12} />
                Image Quality: Clear
              </span>
            </div>
            <div className="space-y-1.5 pt-1">
              <p className="flex items-center gap-2 font-medium">
                <Icon name="scan" size={13} className="text-[#24825C]" />
                Resolution: Optimal
              </p>
              <p className="flex items-center gap-2 text-[#5A7569]">
                <span className="flex h-3.5 w-3.5 items-center justify-center rounded-full bg-[#DFF1E8] text-[#24825C]">
                  <Icon name="check" size={9} />
                </span>
                Scan Complete
              </p>
            </div>
            <div className="mx-auto mt-3 h-1 w-16 rounded-full bg-[#D7E3DC]" />
          </div>
        </div>

        {/* Left floating trend glass card */}
        <div className="absolute bottom-24 left-3 z-20 hidden w-[142px] rounded-2xl border border-white/90 bg-white/80 p-3 shadow-[0_14px_30px_-14px_rgba(16,56,42,0.28)] backdrop-blur-md sm:block">
          <div className="mb-2 h-1.5 w-14 rounded-full bg-[#4F8D72]/70" />
          <svg className="h-12 w-full" viewBox="0 0 120 48" fill="none">
            <path d="M0 14h120M0 28h120M0 42h120" stroke="#D9E8E0" strokeWidth="1" />
            <path d="M4 34C20 34 24 22 40 24C56 26 62 15 78 18C94 21 102 10 116 12V46H4Z" fill="#2A8661" fillOpacity="0.14" />
            <path d="M4 34C20 34 24 22 40 24C56 26 62 15 78 18C94 21 102 10 116 12" stroke="#1E6B4D" strokeWidth="2.2" strokeLinecap="round" />
          </svg>
          <div className="mt-2 flex gap-1.5">
            <span className="h-1.5 w-8 rounded-full bg-[#C9DDD2]" />
            <span className="h-1.5 w-12 rounded-full bg-[#E1EFE7]" />
          </div>
        </div>

        {/* Right floating summary glass card */}
        <div className="absolute right-3 top-[34%] z-20 hidden w-[132px] rounded-2xl border border-white/90 bg-white/80 p-3 shadow-[0_14px_30px_-14px_rgba(16,56,42,0.28)] backdrop-blur-md sm:block">
          <div className="flex items-center gap-2">
            <span className="h-3.5 w-3.5 rounded bg-[#9BCAB4]/70" />
            <span className="h-2 w-16 rounded-full bg-[#4A8168]/75" />
          </div>
          <div className="mt-2.5 space-y-1.5">
            <div className="h-1.5 w-full rounded-full bg-[#CFE1D7]" />
            <div className="h-1.5 w-4/5 rounded-full bg-[#DDEBE3]" />
            <div className="h-1.5 w-3/5 rounded-full bg-[#E6F2EB]" />
          </div>
        </div>
      </div>
    </div>
  );
}
