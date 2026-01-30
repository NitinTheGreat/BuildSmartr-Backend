-- ============================================================================
-- QUOTE FEATURE MIGRATION
-- Run this SQL in your Supabase SQL Editor
-- ============================================================================

-- ============================================================================
-- 1. SEGMENTS TABLE - Master list of trade segments with benchmark pricing
-- ============================================================================
CREATE TABLE IF NOT EXISTS segments (
    id text PRIMARY KEY,
    name text NOT NULL,
    phase text NOT NULL,
    phase_order int NOT NULL,
    benchmark_low numeric(10,2),
    benchmark_high numeric(10,2),
    benchmark_unit text DEFAULT '$/sf',
    notes text,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_segments_phase ON segments(phase_order);

-- ============================================================================
-- 2. VENDOR_SERVICES TABLE - One row per vendor-segment combination
-- ============================================================================
CREATE TABLE IF NOT EXISTS vendor_services (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_email text NOT NULL REFERENCES user_info(email) ON DELETE CASCADE,
    company_name text NOT NULL,
    segment text NOT NULL REFERENCES segments(id),
    countries_served text[] NOT NULL DEFAULT ARRAY['CA'],
    regions_served text[] NOT NULL DEFAULT ARRAY[]::text[],
    pricing_rules text,
    lead_time text,
    notes text,
    is_active boolean DEFAULT true,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    
    CONSTRAINT unique_vendor_segment UNIQUE(user_email, segment)
);

CREATE INDEX IF NOT EXISTS idx_vendor_services_segment ON vendor_services(segment) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_vendor_services_countries ON vendor_services USING GIN(countries_served) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_vendor_services_regions ON vendor_services USING GIN(regions_served) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_vendor_services_user ON vendor_services(user_email);

-- ============================================================================
-- 3. QUOTE_REQUESTS TABLE - Tracks each quote request
-- ============================================================================
CREATE TABLE IF NOT EXISTS quote_requests (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    chat_id uuid REFERENCES chats(id) ON DELETE SET NULL,
    requested_by_user_id uuid NOT NULL,
    
    -- Request details
    segment text NOT NULL REFERENCES segments(id),
    project_sqft integer NOT NULL,
    options jsonb DEFAULT '{}',
    
    -- Frozen address at request time
    address_snapshot jsonb NOT NULL,
    
    -- Processing status
    status text DEFAULT 'matching_vendors',
    -- Values: 'matching_vendors', 'generating_quotes', 'completed', 'failed'
    
    -- Results
    matched_vendors jsonb,
    vendor_quotes jsonb,
    iivy_benchmark jsonb,
    
    -- Metadata
    created_at timestamptz DEFAULT now(),
    completed_at timestamptz,
    error_message text
);

CREATE INDEX IF NOT EXISTS idx_quote_requests_project ON quote_requests(project_id);
CREATE INDEX IF NOT EXISTS idx_quote_requests_user ON quote_requests(requested_by_user_id);
CREATE INDEX IF NOT EXISTS idx_quote_requests_status ON quote_requests(status) WHERE status != 'completed';

-- ============================================================================
-- 4. ADD STRUCTURED ADDRESS COLUMNS TO PROJECTS TABLE
-- ============================================================================
ALTER TABLE projects ADD COLUMN IF NOT EXISTS address_street text;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS address_city text;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS address_region text;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS address_country text DEFAULT 'CA';
ALTER TABLE projects ADD COLUMN IF NOT EXISTS address_postal text;

-- ============================================================================
-- 5. ADD COMPANY_NAME TO USER_INFO TABLE
-- ============================================================================
ALTER TABLE user_info ADD COLUMN IF NOT EXISTS company_name text;

-- ============================================================================
-- 6. INSERT SEGMENTS DATA (100+ trade segments)
-- ============================================================================
INSERT INTO segments (id, name, phase, phase_order, benchmark_low, benchmark_high, benchmark_unit, notes) VALUES

-- Phase 1: Pre-design / Due Diligence
('general_contractor', 'General Contractor', 'Pre-design / Due Diligence', 1, 45.00, 70.00, '$/sf', '10% of construction cost'),
('land_surveyor', 'Land surveyor (boundary/topo/as-built)', 'Pre-design / Due Diligence', 1, 0.50, 0.50, '$/sf', NULL),
('geotechnical_engineer', 'Geotechnical engineer / soils testing', 'Pre-design / Due Diligence', 1, 0.60, 1.40, '$/sf', NULL),
('environmental_consultant', 'Environmental consultant (Phase I/II, asbestos/lead, contamination)', 'Pre-design / Due Diligence', 1, 0.80, 1.60, '$/sf', 'Phase II can be large additional cost'),
('arborist', 'Arborist / tree survey', 'Pre-design / Due Diligence', 1, 0.20, 0.80, '$/sf', NULL),
('civil_engineer', 'Civil engineer (site grading/stormwater/servicing)', 'Pre-design / Due Diligence', 1, 2.00, 6.00, '$/sf', NULL),
('structural_engineer', 'Structural engineer (early input)', 'Pre-design / Due Diligence', 1, 3.20, 8.00, '$/sf', NULL),
('energy_advisor', 'Energy advisor / code consultant', 'Pre-design / Due Diligence', 1, 0.24, 0.72, '$/sf', NULL),
('demolition_contractor', 'Demolition contractor', 'Pre-design / Due Diligence', 1, 6.00, 15.00, '$/sf', 'If teardown'),
('hazmat_abatement', 'Hazardous materials abatement contractor', 'Pre-design / Due Diligence', 1, 2.00, 8.00, '$/sf', 'If needed'),
('utility_locate', 'Utility locate service', 'Pre-design / Due Diligence', 1, 0.04, 0.12, '$/sf', 'Before digging'),

-- Phase 2: Design / Approvals / Preconstruction
('architect', 'Architect / residential designer', 'Design / Approvals / Preconstruction', 2, 48.15, 112.35, '$/sf', 'AIBC net % fee scale'),
('draftsperson', 'Draftsperson / BIM/CAD technician', 'Design / Approvals / Preconstruction', 2, 2.00, 10.00, '$/sf', NULL),
('landscape_architect', 'Landscape architect/designer', 'Design / Approvals / Preconstruction', 2, 0.80, 4.00, '$/sf', 'Optional early'),
('permit_expeditor', 'Permit expeditor / planning consultant', 'Design / Approvals / Preconstruction', 2, 22.40, 37.60, '$/sf', 'Optional'),
('quantity_surveyor', 'Quantity surveyor / estimator', 'Design / Approvals / Preconstruction', 2, 0.80, 3.20, '$/sf', 'Optional'),
('construction_manager', 'General contractor / construction manager', 'Design / Approvals / Preconstruction', 2, 45.00, 70.00, '$/sf', NULL),
('legal_surveyor', 'Legal surveyor / strata/lot line consultant', 'Design / Approvals / Preconstruction', 2, 1.20, 6.00, '$/sf', 'If needed'),
('testing_labs', 'Testing labs / special inspections coordinator', 'Design / Approvals / Preconstruction', 2, 1.22, 1.89, '$/sf', NULL),

-- Phase 3: Site Mobilization & Earthworks
('site_fencing', 'Site fencing / hoarding supplier', 'Site Mobilization & Earthworks', 3, 0.81, 1.26, '$/sf', NULL),
('temp_power', 'Temporary power & lighting contractor', 'Site Mobilization & Earthworks', 3, 1.01, 1.58, '$/sf', NULL),
('temp_water', 'Temporary water / hydrant meter setup', 'Site Mobilization & Earthworks', 3, 0.41, 0.63, '$/sf', NULL),
('portable_toilet', 'Portable toilet service', 'Site Mobilization & Earthworks', 3, 0.20, 0.32, '$/sf', NULL),
('site_security', 'Site security (cameras/guards)', 'Site Mobilization & Earthworks', 3, 0.41, 0.63, '$/sf', 'Optional'),
('waste_hauling', 'Dumpster / waste hauling / recycling', 'Site Mobilization & Earthworks', 3, 1.42, 2.21, '$/sf', NULL),
('tree_clearing', 'Tree clearing / stump grinding', 'Site Mobilization & Earthworks', 3, 0.61, 0.95, '$/sf', NULL),
('excavation', 'Excavation contractor', 'Site Mobilization & Earthworks', 3, 6.48, 10.08, '$/sf', NULL),
('shoring', 'Shoring / underpinning contractor', 'Site Mobilization & Earthworks', 3, 1.22, 1.89, '$/sf', 'If needed'),
('dewatering', 'Dewatering contractor', 'Site Mobilization & Earthworks', 3, 0.61, 0.95, '$/sf', 'If needed'),
('rock_blasting', 'Rock breaking/blasting contractor', 'Site Mobilization & Earthworks', 3, 2.03, 3.15, '$/sf', 'If needed'),
('trucking_soil', 'Trucking / soil disposal / import fill', 'Site Mobilization & Earthworks', 3, 4.45, 6.93, '$/sf', NULL),
('erosion_control', 'Erosion & sediment control contractor', 'Site Mobilization & Earthworks', 3, 0.61, 0.95, '$/sf', NULL),

-- Phase 4: Undergrounds / Services
('storm_sanitary_water', 'Storm/sanitary/water service contractor', 'Undergrounds / Services', 4, 4.45, 6.93, '$/sf', NULL),
('septic_system', 'Septic system designer & installer', 'Undergrounds / Services', 4, 8.00, 18.00, '$/sf', 'If not on sewer'),
('well_driller', 'Well driller & pump installer', 'Undergrounds / Services', 4, 4.00, 12.00, '$/sf', 'If not on city water'),
('drain_tile', 'Drain tile / perimeter drainage contractor', 'Undergrounds / Services', 4, 2.43, 3.78, '$/sf', NULL),
('utility_contractors', 'Utility contractors (electrical/gas/telecom)', 'Undergrounds / Services', 4, 3.24, 5.04, '$/sf', NULL),
('site_testing', 'Site inspection/testing services (compaction, materials)', 'Undergrounds / Services', 4, 1.62, 2.52, '$/sf', NULL),

-- Phase 5: Foundations / Slab
('formwork', 'Formwork contractor', 'Foundations / Slab', 5, 6.48, 10.08, '$/sf', NULL),
('rebar', 'Rebar supplier/installer', 'Foundations / Slab', 5, 3.65, 5.67, '$/sf', NULL),
('concrete_supplier', 'Concrete supplier (ready-mix)', 'Foundations / Slab', 5, 7.29, 11.34, '$/sf', NULL),
('concrete_placing', 'Concrete placing/finishing crew', 'Foundations / Slab', 5, 3.65, 5.67, '$/sf', NULL),
('waterproofing', 'Waterproofing / dampproofing contractor', 'Foundations / Slab', 5, 2.84, 4.41, '$/sf', NULL),
('foundation_insulation', 'Foundation insulation contractor', 'Foundations / Slab', 5, 1.62, 2.52, '$/sf', NULL),
('sump_pump', 'Sump pump installer', 'Foundations / Slab', 5, 0.41, 0.63, '$/sf', 'If needed'),
('concrete_cutting', 'Concrete cutting/core drilling', 'Foundations / Slab', 5, 0.41, 0.63, '$/sf', 'As needed'),

-- Phase 6: Framing / Structure
('lumber_supplier', 'Lumber/material supplier', 'Framing / Structure', 6, 18.23, 28.35, '$/sf', NULL),
('framing_crew', 'Framing crew (carpenters)', 'Framing / Structure', 6, 20.25, 31.50, '$/sf', NULL),
('engineered_beams', 'Engineered floor/beam supplier (LVL/PSL/glulam)', 'Framing / Structure', 6, 6.08, 9.45, '$/sf', NULL),
('roof_trusses', 'Roof truss supplier & installer', 'Framing / Structure', 6, 10.53, 16.38, '$/sf', NULL),
('steel_fabricator', 'Steel fabricator/erector', 'Framing / Structure', 6, 1.62, 2.52, '$/sf', 'If steel'),
('crane_service', 'Crane / boom truck service', 'Framing / Structure', 6, 2.03, 3.15, '$/sf', 'As needed'),
('fasteners', 'Fastener/hardware supplier', 'Framing / Structure', 6, 3.24, 5.04, '$/sf', NULL),
('rough_stairs', 'Stairs/framing stair builder (rough)', 'Framing / Structure', 6, 2.43, 3.78, '$/sf', NULL),

-- Phase 7: Building Enclosure (Dry-in)
('windows_exterior_doors', 'Window & exterior door supplier/installer', 'Building Enclosure', 7, 12.15, 18.90, '$/sf', NULL),
('garage_doors', 'Garage door supplier/installer', 'Building Enclosure', 7, 2.84, 4.41, '$/sf', NULL),
('roofing', 'Roofing contractor', 'Building Enclosure', 7, 14.18, 22.05, '$/sf', NULL),
('sheet_metal', 'Sheet metal (gutters/downspouts/flashing)', 'Building Enclosure', 7, 2.43, 3.78, '$/sf', NULL),
('building_wrap', 'Building wrap / air barrier installer', 'Building Enclosure', 7, 2.84, 4.41, '$/sf', NULL),
('exterior_insulation', 'Exterior insulation contractor', 'Building Enclosure', 7, 2.43, 3.78, '$/sf', 'As needed'),
('siding', 'Siding/cladding contractor', 'Building Enclosure', 7, 10.94, 17.01, '$/sf', NULL),
('stucco_eifs', 'Stucco / EIFS contractor', 'Building Enclosure', 7, 2.84, 4.41, '$/sf', 'If applicable'),
('masonry', 'Masonry contractor (brick/stone/veneer/chimney)', 'Building Enclosure', 7, 1.62, 2.52, '$/sf', NULL),
('deck_membrane', 'Deck membrane / balcony waterproofing', 'Building Enclosure', 7, 1.22, 1.89, '$/sf', NULL),
('exterior_caulking', 'Exterior caulking/sealant contractor', 'Building Enclosure', 7, 0.81, 1.26, '$/sf', NULL),

-- Phase 8: Rough-ins (MEP)
('plumbing_rough', 'Plumbing contractor (rough) + supply', 'Rough-ins (MEP)', 8, 24.30, 37.80, '$/sf', NULL),
('hvac', 'HVAC contractor (ducting, rough equipment)', 'Rough-ins (MEP)', 8, 22.68, 35.28, '$/sf', NULL),
('gas_fitter', 'Gas fitter', 'Rough-ins (MEP)', 8, 1.22, 1.89, '$/sf', 'Often HVAC/plumbing'),
('electrical_rough', 'Electrical contractor (rough wiring) + supply', 'Rough-ins (MEP)', 8, 24.71, 38.43, '$/sf', NULL),
('low_voltage', 'Low-voltage contractor (data, AV, intercom)', 'Rough-ins (MEP)', 8, 2.03, 3.15, '$/sf', NULL),
('security_alarm', 'Security/alarm contractor', 'Rough-ins (MEP)', 8, 0.81, 1.26, '$/sf', 'Optional'),
('smart_home', 'Smart home / automation contractor', 'Rough-ins (MEP)', 8, 0.81, 1.26, '$/sf', 'Optional'),
('central_vacuum', 'Central vacuum installer', 'Rough-ins (MEP)', 8, 0.41, 0.63, '$/sf', 'Optional'),
('fire_sprinkler', 'Fire sprinkler contractor', 'Rough-ins (MEP)', 8, 0.81, 1.26, '$/sf', 'If required'),
('elevator', 'Elevator contractor', 'Rough-ins (MEP)', 8, 16.00, 40.00, '$/sf', 'Optional'),
('fireplace', 'Chimney/fireplace installer (gas/wood)', 'Rough-ins (MEP)', 8, 1.62, 2.52, '$/sf', 'If applicable'),

-- Phase 9: Insulation / Air-sealing / Drywall
('insulation', 'Insulation contractor (batts/spray foam/blown-in)', 'Insulation / Drywall', 9, 4.86, 7.56, '$/sf', NULL),
('air_sealing', 'Air-sealing/energy detailing crew', 'Insulation / Drywall', 9, 1.42, 2.21, '$/sf', NULL),
('vapor_barrier', 'Vapor barrier installer', 'Insulation / Drywall', 9, 0.20, 0.32, '$/sf', 'Where applicable'),
('drywall_supply', 'Drywall supplier', 'Insulation / Drywall', 9, 2.43, 3.78, '$/sf', NULL),
('drywall_hanging', 'Drywall hanging crew', 'Insulation / Drywall', 9, 6.08, 9.45, '$/sf', NULL),
('drywall_taping', 'Tapers/mudders', 'Insulation / Drywall', 9, 4.86, 7.56, '$/sf', NULL),
('soundproofing', 'Acoustic/soundproofing contractor', 'Insulation / Drywall', 9, 0.81, 1.26, '$/sf', 'Optional'),

-- Phase 10: Interior Finishes
('interior_doors', 'Interior door supplier/installer', 'Interior Finishes', 10, 2.84, 4.41, '$/sf', NULL),
('finish_carpenters', 'Finish carpenters (trim, baseboards, casings)', 'Interior Finishes', 10, 6.48, 10.08, '$/sf', NULL),
('stair_finish', 'Stair finish carpenter / railing contractor', 'Interior Finishes', 10, 2.43, 3.78, '$/sf', NULL),
('cabinets', 'Cabinet maker / kitchen & bath millwork', 'Interior Finishes', 10, 12.56, 19.53, '$/sf', NULL),
('countertops', 'Countertop fabricator/installer', 'Interior Finishes', 10, 5.67, 8.82, '$/sf', NULL),
('tile', 'Tile supplier/installer', 'Interior Finishes', 10, 4.86, 7.56, '$/sf', NULL),
('flooring', 'Flooring contractor', 'Interior Finishes', 10, 9.72, 15.12, '$/sf', NULL),
('painter', 'Painter (prime/paint)', 'Interior Finishes', 10, 10.13, 15.75, '$/sf', NULL),
('wallpaper', 'Wallpaper installer', 'Interior Finishes', 10, 0.20, 0.32, '$/sf', 'Optional'),
('shower_glass', 'Glass/shower door contractor', 'Interior Finishes', 10, 2.03, 3.15, '$/sf', NULL),
('fireplace_finish', 'Fireplace finishing (mantels/surrounds)', 'Interior Finishes', 10, 0.81, 1.26, '$/sf', NULL),
('closet_organizer', 'Closet organizer contractor', 'Interior Finishes', 10, 0.20, 0.32, '$/sf', 'Optional'),
('mirrors', 'Mirror supplier/installer', 'Interior Finishes', 10, 0.41, 0.63, '$/sf', NULL),
('specialty_metal', 'Specialty metalwork (railings, custom steel)', 'Interior Finishes', 10, 0.41, 0.63, '$/sf', 'Optional'),

-- Phase 11: Exterior Works / Site Finishes
('concrete_flatwork', 'Concrete flatwork (walks, patios, driveway, steps)', 'Exterior Works', 11, 4.45, 6.93, '$/sf', NULL),
('asphalt_paving', 'Asphalt paving contractor', 'Exterior Works', 11, 1.62, 2.52, '$/sf', 'If asphalt drive'),
('pavers', 'Pavers/stone hardscape contractor', 'Exterior Works', 11, 1.82, 2.84, '$/sf', NULL),
('fencing', 'Fencing/gates contractor', 'Exterior Works', 11, 1.62, 2.52, '$/sf', NULL),
('retaining_walls', 'Retaining wall contractor', 'Exterior Works', 11, 2.43, 3.78, '$/sf', NULL),
('irrigation', 'Irrigation contractor', 'Exterior Works', 11, 0.81, 1.26, '$/sf', NULL),
('landscaping', 'Landscaping contractor (soil, sod, planting)', 'Exterior Works', 11, 4.05, 6.30, '$/sf', NULL),
('landscape_lighting', 'Landscape lighting contractor', 'Exterior Works', 11, 0.20, 0.32, '$/sf', 'Optional'),
('exterior_carpentry', 'Exterior carpentry (decks, pergolas)', 'Exterior Works', 11, 3.65, 5.67, '$/sf', NULL),
('pool', 'Pool/hot tub contractor', 'Exterior Works', 11, 32.00, 80.00, '$/sf', 'Optional'),
('exterior_painting', 'Exterior painting/staining', 'Exterior Works', 11, 0.81, 1.26, '$/sf', 'If needed'),

-- Phase 12: Final Fixtures / Commissioning / Close-out
('plumbing_fixtures', 'Plumber (fixture set: toilets, faucets, trim)', 'Final / Commissioning', 12, 5.67, 8.82, '$/sf', NULL),
('electrical_final', 'Electrician (devices, lights, final connections)', 'Final / Commissioning', 12, 4.45, 6.93, '$/sf', NULL),
('hvac_final', 'HVAC (start-up, balancing, thermostats)', 'Final / Commissioning', 12, 2.03, 3.15, '$/sf', NULL),
('appliances', 'Appliance supplier/installer', 'Final / Commissioning', 12, 7.29, 11.34, '$/sf', NULL),
('shower_glass_final', 'Shower glass final / mirrors final', 'Final / Commissioning', 12, 0.40, 1.60, '$/sf', NULL),
('finish_hardware', 'Finish hardware supplier/installer', 'Final / Commissioning', 12, 2.43, 3.78, '$/sf', NULL),
('cleaning', 'Cleaning crew (construction clean)', 'Final / Commissioning', 12, 2.84, 4.41, '$/sf', NULL),
('pest_control', 'Pest control', 'Final / Commissioning', 12, 0.10, 0.30, '$/sf', 'Optional'),
('testing_commissioning', 'Testing/commissioning (blower door, HVAC balancing)', 'Final / Commissioning', 12, 1.22, 1.89, '$/sf', NULL),
('final_grading', 'Final grading / touch-ups / deficiencies crew', 'Final / Commissioning', 12, 2.84, 4.41, '$/sf', NULL),
('final_survey', 'Surveyor (final as-built / certificate)', 'Final / Commissioning', 12, 0.81, 1.26, '$/sf', 'If needed')

ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    phase = EXCLUDED.phase,
    phase_order = EXCLUDED.phase_order,
    benchmark_low = EXCLUDED.benchmark_low,
    benchmark_high = EXCLUDED.benchmark_high,
    benchmark_unit = EXCLUDED.benchmark_unit,
    notes = EXCLUDED.notes;

-- ============================================================================
-- 7. ROW LEVEL SECURITY POLICIES
-- ============================================================================

-- Enable RLS on new tables
ALTER TABLE segments ENABLE ROW LEVEL SECURITY;
ALTER TABLE vendor_services ENABLE ROW LEVEL SECURITY;
ALTER TABLE quote_requests ENABLE ROW LEVEL SECURITY;

-- Segments: Anyone can read
CREATE POLICY "Segments are viewable by everyone" ON segments
    FOR SELECT USING (true);

-- Vendor Services: Users can manage their own
CREATE POLICY "Users can view all active vendor services" ON vendor_services
    FOR SELECT USING (is_active = true);

CREATE POLICY "Users can manage their own vendor services" ON vendor_services
    FOR ALL USING (user_email = auth.jwt() ->> 'email');

-- Quote Requests: Users can view their own and quotes for their projects
CREATE POLICY "Users can view quote requests for their projects" ON quote_requests
    FOR SELECT USING (
        requested_by_user_id = auth.uid()
        OR project_id IN (SELECT id FROM projects WHERE user_id = auth.uid())
    );

CREATE POLICY "Users can create quote requests" ON quote_requests
    FOR INSERT WITH CHECK (requested_by_user_id = auth.uid());

-- ============================================================================
-- VERIFICATION QUERIES
-- Run these after migration to verify:
-- ============================================================================
-- SELECT COUNT(*) FROM segments;  -- Should be ~100
-- SELECT * FROM segments WHERE phase_order = 7;  -- Building Enclosure segments
-- \d vendor_services  -- Check table structure
-- \d quote_requests   -- Check table structure
-- SELECT column_name FROM information_schema.columns WHERE table_name = 'projects' AND column_name LIKE 'address_%';
